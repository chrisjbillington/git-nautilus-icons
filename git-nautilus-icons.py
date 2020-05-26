#####################################################################
#                                                                   #
# Copyright 2016, Chris Billington                                  #
#                                                                   #
# This file is part of the git-nautilus-icons project (see          #
#  https://github.com/chrisjbillington/git_nautilus_icons) and is   #
# licensed under the Simplified BSD License. See LICENSE in         #
# the root directory of the project for the full license.           #
#                                                                   #
#####################################################################

from __future__ import print_function, unicode_literals
import sys
import os
import pathlib
from enum import IntEnum, unique
from subprocess import Popen, PIPE, CalledProcessError, check_call
from collections import defaultdict
import socket
import threading
import tempfile
from binascii import hexlify
try:
    from multiprocessing.connection import Connection
except ImportError:
    from _multiprocessing import Connection

import gi
from gi.repository import GObject

PY2 = sys.version_info.major == 2

# A string in sys.argv so that the worker process can identify itself:
WORKER_ARG = 'git-nautilus-icons-worker'
if WORKER_ARG not in sys.argv:
    # Only import the extension modules if we are not the worker process
    if sys.argv[0] == 'nemo':
        gi.require_version('Nemo', '3.0')
        from gi.repository import Nemo as Nautilus
    elif sys.argv[0] == 'caja':
        gi.require_version('Caja', '2.0')
        from gi.repository import Caja as Nautilus
    else:
        gi.require_version('Nautilus', '3.0')
        from gi.repository import Nautilus


BLACKLIST_TEMPLATE = """# git-{nautilus,nemo,caja}-icons blacklist file.
#
# The extension will ignore files in any directories listed in this file, and any of
# their subdirectories.
#
# Blank lines and lines beginning with '#' will be ignored. A '#' character within a
# line will be treated as part of the directory path, so end-of-line comments are not
# allowed.

# Example:
/home/chrisjbillington/clones/example_repo.git

# Another example:
/home/chrisjbillington/clones/some_other_example_huge_repo.git
"""

# Make blacklist file if it doesn't exist:
_conf = os.getenv('XDG_CONFIG_HOME', os.path.join(os.getenv('HOME'), '.config'))
BLACKLIST_FILE = os.path.join(_conf, 'git-nautilus-icons', 'blacklist.conf')
if not os.path.exists(BLACKLIST_FILE):
    # Backcompat for before the rename:
    OLD_BLACKLIST_FILE = os.path.join(_conf, 'git_nautilus_icons', 'blacklist.conf')
    if os.path.exists(OLD_BLACKLIST_FILE):
        BLACKLIST_FILE = OLD_BLACKLIST_FILE
if not os.path.exists(BLACKLIST_FILE):
    check_call(['mkdir', '-p', os.path.dirname(BLACKLIST_FILE)])
    with open(BLACKLIST_FILE, 'w') as f:
        f.write(BLACKLIST_TEMPLATE)

blacklist = []

with open(BLACKLIST_FILE) as f:
    for line in f.readlines():
        line = line.strip()
        if line and not line.startswith('#'):
            if not line.endswith('/'):
                line += '/'
            blacklist.append(line)

DEBUG = False

def blacklisted(path):
    path += '/'
    if any(path.startswith(s + '/') for s in blacklist):
        if DEBUG:
            print('path is blacklisted:', path)
        return True
    return False


# Constants to represent requests and information between parent and child. Not an enum
# because they don't survive pickling between processes in the way we're doing it.
SEND_READY = 0
STILL_WORKING = 1
ALL_DONE = 2
ACK = 4

# For printing the above:
STATUS = {
    SEND_READY: 'SEND_READY',
    STILL_WORKING: 'STILL_WORKING',
    ALL_DONE: 'ALL_DONE',
    ACK: 'ACK',
}


@unique
class SyncStatus(IntEnum):
    """Possible statuses for a repository's sync state."""

    ERROR = -1
    NOT_AHEAD = 0
    AHEAD = 1


@unique
class RepoStatus(IntEnum):
    """Whether a folder is a git repo"""
    ERROR = -1
    NOT_A_REPO = 0
    IS_A_REPO = 1


@unique
class IndexStatus(IntEnum):
    """Possible statuses for a file in the index, ordered by severity. Severiy
    also consistent with being sorted against WorktreeStatus"""
    ERROR = -1
    NOT_IN_INDEX = 0
    CLEAN = 1
    ADDED = 3
    RENAMED = 4
    DELETED = 5
    MODIFIED = 6


@unique
class WorktreeStatus(IntEnum):
    """Possible statuses for a file in the work tree, ordered by severity
    Severiy also consistent with being sorted against IndexStatus"""
    ERROR = -1
    IGNORED = 0
    CLEAN = 1
    UNTRACKED = 2
    DELETED = 5
    MODIFIED = 6
    UNMERGED = 7
    IS_DOT_GIT = 8


@unique
class MergeStatus(IntEnum):
    """Possible statuses for an unmerged file, ordered by severity"""
    ERROR = -1
    NO_CONFLICT = 0
    THEY_DELETED = 1
    WE_DELETED = 2
    BOTH_ADDED = 3
    BOTH_MODIFIED = 4


STATUS_CODES = {
                # Possible statuses returned by 'git status -z':
                ' M': (IndexStatus.CLEAN, WorktreeStatus.MODIFIED, MergeStatus.NO_CONFLICT),
                'MM': (IndexStatus.MODIFIED, WorktreeStatus.MODIFIED, MergeStatus.NO_CONFLICT),
                'AM': (IndexStatus.ADDED, WorktreeStatus.MODIFIED, MergeStatus.NO_CONFLICT),
                'RM': (IndexStatus.RENAMED, WorktreeStatus.MODIFIED, MergeStatus.NO_CONFLICT),
                'M ': (IndexStatus.MODIFIED, WorktreeStatus.CLEAN, MergeStatus.NO_CONFLICT),
                'R ': (IndexStatus.RENAMED, WorktreeStatus.CLEAN, MergeStatus.NO_CONFLICT),
                'A ': (IndexStatus.ADDED, WorktreeStatus.CLEAN, MergeStatus.NO_CONFLICT),
                'D ': (IndexStatus.DELETED, WorktreeStatus.CLEAN, MergeStatus.NO_CONFLICT),
                ' D': (IndexStatus.CLEAN, WorktreeStatus.DELETED, MergeStatus.NO_CONFLICT),
                'MD': (IndexStatus.MODIFIED, WorktreeStatus.DELETED, MergeStatus.NO_CONFLICT),
                'AD': (IndexStatus.ADDED, WorktreeStatus.DELETED, MergeStatus.NO_CONFLICT),
                'RD': (IndexStatus.RENAMED, WorktreeStatus.DELETED, MergeStatus.NO_CONFLICT),
                'UD': (IndexStatus.CLEAN, WorktreeStatus.UNMERGED, MergeStatus.THEY_DELETED),
                'DU': (IndexStatus.CLEAN, WorktreeStatus.UNMERGED, MergeStatus.WE_DELETED),
                'AA': (IndexStatus.CLEAN, WorktreeStatus.UNMERGED, MergeStatus.BOTH_ADDED),
                'UU': (IndexStatus.CLEAN, WorktreeStatus.UNMERGED, MergeStatus.BOTH_MODIFIED),
                '??': (IndexStatus.NOT_IN_INDEX, WorktreeStatus.UNTRACKED, MergeStatus.NO_CONFLICT),
                '!!': (IndexStatus.NOT_IN_INDEX, WorktreeStatus.IGNORED, MergeStatus.NO_CONFLICT),

                # Some extra ones I'm adding for convenience:

                # When a tracked file listed in 'git ls-tree' is not present
                # in the output of 'git status -z', then we assume it is
                # unmodified and use this status:
                'CLEAN': (IndexStatus.CLEAN, WorktreeStatus.CLEAN, MergeStatus.NO_CONFLICT),

                # When a file appears twice in 'git status -z', once with 'D '
                # and once with '??', because it is staged for deletion but
                # nontheless present in the worktree, we use this status:
                'D?': (IndexStatus.DELETED, WorktreeStatus.UNTRACKED, MergeStatus.NO_CONFLICT),

                # When my code doesn't know what do do because it finds a file
                # git doesn't tell it about, or because a file appears twice
                # but not in the manner handled above, then we use this
                # status:
                'ERROR': (IndexStatus.ERROR, WorktreeStatus.ERROR, MergeStatus.ERROR),

                'IS_DOT_GIT': (IndexStatus.CLEAN, WorktreeStatus.IS_DOT_GIT, MergeStatus.NO_CONFLICT)}


# The status of the files in the 'icon_testing_dir' directory, hard coded to
# demonstrate what different statuses look like:
EXAMPLE_FILE_STATUSES = {'01 clean repo': (SyncStatus.NOT_AHEAD, RepoStatus.IS_A_REPO) + STATUS_CODES['CLEAN'],
                         '02 clean repo ahead of remote':
                             (SyncStatus.AHEAD, RepoStatus.IS_A_REPO) + STATUS_CODES['CLEAN'],
                         '03 ignored': STATUS_CODES['!!'],
                         '04 clean': STATUS_CODES['CLEAN'],
                         '05 untracked': STATUS_CODES['??'],
                         '06 unstaged changes': STATUS_CODES[' M'],
                         '07 unstaged deletion': STATUS_CODES[' D'],
                         '08 staged changes': STATUS_CODES['M '],
                         '09 staged rename': STATUS_CODES['R '],
                         '10 staged new file': STATUS_CODES['A '],
                         '11 staged deletion': STATUS_CODES['D '],
                         '12 staged deletion, restored in work tree': STATUS_CODES['D?'],
                         '13 staged and unstaged changes': STATUS_CODES['MM'],
                         '14 staged rename, unstaged changes': STATUS_CODES['RM'],
                         '15 staged new file, unstaged changes': STATUS_CODES['AM'],
                         '16 staged changes, unstaged deletion': STATUS_CODES['MD'],
                         '17 staged rename, unstaged deletion': STATUS_CODES['RD'],
                         '18 staged new file, unstaged deletion': STATUS_CODES['AD'],
                         '19 unmerged, both added': STATUS_CODES['AA'],
                         '20 unmerged, both modified': STATUS_CODES['UU'],
                         '21 unmerged, changed by them, deleted by us': STATUS_CODES['DU'],
                         '22 unmerged, changed by us, deleted by them': STATUS_CODES['UD'],
                         '23 repo with clean index and untracked files':
                             (SyncStatus.NOT_AHEAD, RepoStatus.IS_A_REPO,
                              IndexStatus.CLEAN, WorktreeStatus.UNTRACKED, MergeStatus.NO_CONFLICT),
                         '24 repo with staged and unstaged deletions':
                             (SyncStatus.NOT_AHEAD, RepoStatus.IS_A_REPO,
                              IndexStatus.DELETED, WorktreeStatus.DELETED, MergeStatus.NO_CONFLICT),
                         }

ICON_TESTING_DIR = 'git_nautilus_icons/icon_testing_dir'


def example_statuses(path):
    return {os.path.join(path, name): value for name, value in EXAMPLE_FILE_STATUSES.items()}


def get_icon(status):
    if len(status) == 3:
        # It's a file
        index_status, worktree_status, merge_status = status
        if worktree_status == WorktreeStatus.IS_DOT_GIT:
            return 'git-dotgit'
        sync_status = SyncStatus.NOT_AHEAD
        repo_status = RepoStatus.NOT_A_REPO
    elif len(status) == 5:
        # It's a repo
        sync_status, repo_status, index_status, worktree_status, merge_status = status
    else:
        sys.stderr.write("invalid length of status tuple {}\n".format(len(status)))
    sub_icons = []
    if sync_status is SyncStatus.AHEAD:
        sub_icons.append('ahead')
    if repo_status is RepoStatus.IS_A_REPO:
        sub_icons.append('repo')
    if worktree_status is WorktreeStatus.UNMERGED:
        if merge_status is MergeStatus.THEY_DELETED:
            sub_icons.append('unmerged-modified')
            sub_icons.append('unmerged-deleted')
        elif merge_status is MergeStatus.WE_DELETED:
            sub_icons.append('unmerged-deleted')
            sub_icons.append('unmerged-modified')
        elif merge_status is MergeStatus.BOTH_ADDED:
            sub_icons.append('unmerged-added')
            sub_icons.append('unmerged-added')
        elif merge_status is MergeStatus.BOTH_MODIFIED:
            sub_icons.append('unmerged-modified')
            sub_icons.append('unmerged-modified')
    # We only show index clean if work tree is untracked (only applies for directories/repos):
    else:
        if index_status is IndexStatus.CLEAN and worktree_status is WorktreeStatus.UNTRACKED:
            sub_icons.append('clean')
        elif index_status is IndexStatus.ADDED:
            sub_icons.append('added')
        elif index_status is IndexStatus.RENAMED:
            sub_icons.append('renamed')
        elif index_status is IndexStatus.DELETED:
            sub_icons.append('deleted')
        elif index_status is IndexStatus.MODIFIED:
            sub_icons.append('modified')
        if worktree_status is WorktreeStatus.CLEAN:
            sub_icons.append('clean')
        elif worktree_status is WorktreeStatus.UNTRACKED:
            sub_icons.append('untracked')
        elif worktree_status is WorktreeStatus.DELETED:
            sub_icons.append('deleted')
        elif worktree_status is WorktreeStatus.MODIFIED:
            sub_icons.append('modified')
    if not sub_icons:
        return None
    return 'git-' + '-'.join(sub_icons)


class NotARepo(CalledProcessError):
    pass


class FileStatuses(dict):
    """Dictionary like object which can lookup the status of a file even if
    only a an ancestor directory is listed as having that status, and not the
    file specifically. This is because 'git status' abbreviates its output in
    this way, and telling git to give full output could send it into massive
    directories that neither it nor Nautilus are interested in."""
    def __init__(self, repo_root):
        self.repo_root = repo_root
        dict.__init__(self)

    def get_status(self, path):
        try:
            return dict.__getitem__(self, path)
        except KeyError:
            # Try parent_directories:
            paths_tried = []
            i = 0
            # Really make sure we don't infinitely loop here if I've made a mistake
            while i < 1000:
                i += 1
                if path in ('/', self.repo_root):
                    return STATUS_CODES['ERROR']
                path += '/'
                try:
                    result =  dict.__getitem__(self, path)
                except KeyError:
                    paths_tried.append(path)
                    path = os.path.dirname(os.path.normpath(path))
                else:
                    # Add all the directories we tried already, so that future
                    # lookups from the same starting directory will find their
                    # result sooner:
                    for path in paths_tried:
                        self[path] = result
                    return result
            sys.stderr.write("Looping too long in FileStatuses.__getitem__\n")
            return STATUS_CODES['ERROR']


def git_call(cmd, path):
    """Calls a command with check_output, raising NotARepo if there is no git
    repo there. This lets us avoid the race condition of a repo disappearing
    disappear before we call the command."""
    try:
        proc = Popen(cmd, cwd=path, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
    except OSError:
        # Git not installed, or repo path doesn't exist or isn't a directory.
        raise NotARepo(1, cmd, "Couldn't run git command - path might not exist")
    if proc.returncode:
        # Something went wrong - repo got deleted while we were reading it, or something
        # like that.
        raise NotARepo(proc.returncode, cmd, output=(stdout + stderr))
    return stdout.decode('utf8')


def is_git_repo(path):
    """returns whether a path is a git repo"""
    if blacklisted(path):
        return False
    return os.path.isdir(os.path.join(path, '.git'))


def is_in_work_tree(path):
    """returns whether a path is in the work tree of a git repo (ie, not
    inside .git!)"""
    if blacklisted(path):
        return False
    cmd = ['git', 'rev-parse', '--is-inside-work-tree']
    try:
        return git_call(cmd, path).strip() == 'true'
    except NotARepo:
        return False


def get_repo_root(path):
    """Returns the root directory of a repo, given a directory within it,
    or raises NotARepo if the directory is not in a git repo"""
    if blacklisted(path):
        raise NotARepo
    cmd = ['git', 'rev-parse', '--git-dir']
    output = git_call(cmd, path).strip()
    if output == '.git':
        return path
    else:
        # Otherwise it's given as an absolute path:
        return os.path.dirname(output)


def repo_is_ahead(path):
    """Returns whether the repo at a given path has any unpushed commits"""
    cmd = ['git', 'for-each-ref', '--format="%(push:track)"', 'refs/heads']
    return 'ahead' in git_call(cmd, path)


def get_folder_overall_status(path, file_statuses, all_statuses):
    """Returns a 3-tuple of an IndexStatus, WorktreeStatus and MergeStatus,
    chosen based on the most severe of the corresponding statuses of the
    files. file_statuses should be a set of status tuples for individual
    files."""
    if file_statuses:
        index_statuses, worktree_statuses, merge_statuses = zip(*file_statuses)
        index_status = max(index_statuses)
        worktree_status = max(worktree_statuses)
        merge_status = max(merge_statuses)
    else:
        # No files listed. Maybe the directory, or a parent directory, is listed:
        index_status, worktree_status, merge_status = all_statuses.get_status(path)
    return index_status, worktree_status, merge_status


def get_repo_overall_status(path, statuses):
    """Return the repo's overall status, 5-tuple of a SyncStatus, RepoStatus,
    IndexStatus, WorktreeStatus and MergeStatus. The latter three are chosen
    based on the most severe of the corresponding statuses of the files"""
    if repo_is_ahead(path):
        sync_status = SyncStatus.AHEAD
    else:
        sync_status = SyncStatus.NOT_AHEAD
    repo_status = RepoStatus.IS_A_REPO
    if not statuses:
        # No files! Therefore clean.
        index_status = IndexStatus.CLEAN
        worktree_status = WorktreeStatus.CLEAN
        merge_status = MergeStatus.NO_CONFLICT
    else:
        index_status, worktree_status, merge_status = get_folder_overall_status(
            path, set(statuses.values()), statuses
        )
    return sync_status, repo_status, index_status, worktree_status, merge_status


def function_with_cache(orig_func):
    """Cache results of a function clear cache with func.cache.clear. Does not support
    kwargs."""
    def f(*args):
        try:
            return f.cache[args]
        except KeyError:
            f.cache[(args)] = orig_func(*args)
            return f.cache[args]
    f.cache = {}
    return f


@function_with_cache
def repo_status(path):
    if DEBUG:
        print("repo status:", path)
    """Return the status of the repo overall as well as a dict of the statuses
    of all non-ignored files in it. All files within the work tree but not
    listed in the output have the status of their parent directories.
    Raises NotARepo if the path no longer points to a git repo."""
    repo_root = get_repo_root(path)
    # 'git status' will get all files other than unmodified ones:
    status_command = ['git', 'status', '-z']
    status_output = git_call(status_command, path)
    statuses = FileStatuses(repo_root)
    status_entries = status_output.split('\x00')[:-1]
    i = 0
    while i < len(status_entries):
        status_entry = status_entries[i]
        status = status_entry[0:2]
        # Consider a change in file type (link to non-link or vice-versa) a
        # modification:
        status = status.replace('T', 'M')
        # Consider a copy into a new file to be an addition:
        status = status.replace('C', 'A')
        relpath = status_entry[3:]
        filename = os.path.join(repo_root, relpath)
        if filename in statuses:
            # Same file can be listed twice if for example there is a staged
            # deletion and then the file is re-added:
            if (statuses[filename] == STATUS_CODES['D '] and status == '??'):
                status_tuple = STATUS_CODES['D?']
            else:
                sys.stderr.write("Do not know how to interpret file present twice in 'git status -z' " +
                                 "with statuses '{}' and '{}'\n".format(statuses[filename], status))
                status_tuple = STATUS_CODES['ERROR']
        else:
            status_tuple = STATUS_CODES[status]
        statuses[filename] = status_tuple
        if status[0] == 'R':
            # A rename, the next entry is the original filename. Skip it.
            i += 1
        i += 1
    # And now to get all the unmodified files:
    lstree_command = ['git', 'ls-tree', '--full-tree', '-zr', '--name-only', 'HEAD']
    try:
        lstree_output = git_call(lstree_command, path)
    except CalledProcessError as e:
        if not 'Not a valid object name HEAD' in e.output.decode('utf8'):
            # Ignore if there is no HEAD (no commits probably). Otherwise raise.
            raise
    else:
        lstree_entries = set(lstree_output.split('\x00')[:-1])
        for lstree_relpath in lstree_entries:
            filename = os.path.join(repo_root, lstree_relpath)
            if filename not in statuses:
                statuses[filename] = STATUS_CODES['CLEAN']
    overall_status = get_repo_overall_status(path, statuses)
    return overall_status, statuses


def get_statuses_by_dir(path, file_statuses):
    """Sort the file statuses into which directory at the current level they
    are under. Only keep unique statuses, and return a dictionary of sets for
    each directory rooted at the given path."""
    statuses_by_dir = defaultdict(set)
    prefix = path + '/'
    len_prefix = len(prefix)
    for name, status in file_statuses.items():
        if not name.startswith(prefix):
            continue
        dirname = name[:name.find('/', len_prefix)]
        statuses_by_dir[dirname].add(status)
    return statuses_by_dir


@function_with_cache
def directory_status(path):
    if DEBUG:
        print("directory_status:", path)
    """Returns the statuses for all the files/directories in a given path
    (without recursing). For folders in a repo, their status is given as the
    most severe of their contents. For repositories, their status is given as
    their overall status, which is the same as for a folder but also includes
    whether the repo has unpushed commits or not, as well as the fact that it
    is a repo. For submodules, their overall status is given, but is
    calculated as if the repo contained a file with the status of the
    submodule itself. Thus, if a submodule is itself clean, but is checked out
    at a different commit than recorded by a commit in the parent repo, then
    it will appear as modified."""
    if path.endswith(ICON_TESTING_DIR):
        return example_statuses(path)
    statuses = {}
    if not is_in_work_tree(path):
        # Not in a git repo. Give statuses of any git repos within:
        try:
            subdirs = os.listdir(path)
        except (OSError,FileNotFoundError):
            # Deleted, unmounted, or otherwise gone
            subdirs = []
        for basename in subdirs:
            fullname = os.path.join(path, basename)
            if os.path.isdir(fullname) and is_git_repo(fullname):
                try:
                    status, _ = repo_status(fullname)
                except NotARepo:
                    # Repo deleted
                    continue
            else:
                status = None
            statuses[fullname] = status
        return statuses
    else:
        try:
            _, file_statuses = repo_status(path)
        except NotARepo:
            # Repo deleted
            return {}
        # As an optimisation, collect the set of statuses in each directory at
        # the current level we're at:
        statuses_by_dir = get_statuses_by_dir(path, file_statuses)
        try:
            subdirs = os.listdir(path)
        except (OSError,FileNotFoundError):
            # Deleted, unmounted, or otherwise gone
            subdirs = []
        for basename in subdirs:
            fullname = os.path.join(path, basename)
            if basename == '.git':
                status = STATUS_CODES['IS_DOT_GIT']
            elif not os.path.isdir(fullname):
                # A normal file:
                status = file_statuses.get_status(fullname)
            elif is_git_repo(fullname):
                # A submodule. Give its overall status, calculated as if it
                # contained a file with its own status in the parent repo.
                # This ensures the most severe of the subrepo's own status and
                # its status in the parent repo will be shown.
                file_status = file_statuses.get_status(fullname)
                try:
                    _, subrepo_file_statuses = repo_status(fullname)
                    subrepo_file_statuses.update({fullname: file_status})
                    status = get_repo_overall_status(fullname, subrepo_file_statuses)
                except NotARepo:
                    # subrepo deleted
                    continue
            else:
                # A normal folder. Give its overall
                status = get_folder_overall_status(
                    fullname, statuses_by_dir[fullname], file_statuses
                )
            statuses[fullname] = status
    return statuses


def get_filepath(file):
    """Extract filepath from the URI in a NautilusVFSFile object. Return the
    filepath or None if uri scheme is not 'file'"""
    if sys.version_info.major == 2:
        from urlparse import urlparse
        from urllib import unquote
    else:
        from urllib.parse import urlparse
        from urllib.parse import unquote

    def _checkdecode(s):
        return s.decode('utf8') if isinstance(s, bytes) else s

    parsed_uri = urlparse(file.get_uri())
    if parsed_uri.scheme == 'file':
        netloc = _checkdecode(parsed_uri.netloc)
        path = _checkdecode(unquote(parsed_uri.path))
        return os.path.abspath(os.path.join(netloc, path))


class WorkerProcess(object):
    TIMEOUT = 0.01
    """A separate process for making git status calls without blocking Nautilis's GUI.
    This could have been a thread instead of a process, but nautilus-python has an issue
    where it does not realease the GIL when it has finished running extension code, so
    the interpreter cannot keep running background threads. So no problem, we use a
    separate process instead."""
    def __init__(self, conn):
        self.conn = conn
        # Files whose status we still need to check
        self.pending = set()
        # Files whose status we're waiting to send to the parent process
        self.ready = set()
        self.lock = threading.Lock()
        self.processing_required = threading.Event()
        self.git_status_loop_thread = threading.Thread(target=self.git_status_loop)
        self.git_status_loop_thread.daemon = True
        self.git_status_loop_thread.start()

    def git_status_loop(self):
        """Runs in a thread to get git statuses for files in self.pending, and add them
        to self.ready. Does work until self.pending is empty, and then blocks until
        self.processing_required is set."""
        while True:
            self.processing_required.wait()
            if DEBUG:
                print("worker: git status loop: triggered")
            self.processing_required.clear()
            while self.pending:
                # We process in a chunk so that we can cache git status calls and
                # directory status calls within a chunk, but that new files arriving in
                # the meantime will not use the cache, as it might be invalid by then.
                repo_status.cache.clear()
                directory_status.cache.clear()
                pending = self.pending.copy()
                while pending:
                    path = pending.pop()
                    status = directory_status(os.path.dirname(path)).get(path, None)
                    if status is not None:
                        icon = get_icon(status)
                        if icon is not None:
                            with self.lock:
                                if DEBUG:
                                    print('adding to ready set:', path)
                                self.ready.add((path, icon))
                    self.pending.remove(path)

    def run(self):
        timeout = None
        while True:
            # Block until we get a message. If we get a message with a filepath, set
            # timeout = self.TIMEOUT so that we can detect when files stop coming. This
            # way we can batch our processing. Once messages cease, set timeout = None
            # to block again.
            if self.conn.poll(timeout):
                try:
                    message = self.conn.recv()
                except EOFError:
                    return
                if message == SEND_READY:
                    # Send the parent the details of the filepaths we've processed so
                    # far:
                    with self.lock:
                        if DEBUG:
                            print('worker sending %d processed files' % len(self.ready))
                        if self.pending:
                            status = STILL_WORKING
                        else:
                            status = ALL_DONE
                        self.conn.send((self.ready, status))
                        self.ready = set()
                else:
                    # It's a filepath to be processed, add it to the pile:
                    with self.lock:
                        self.pending.add(message)
                    self.conn.send(ACK)
                    timeout = self.TIMEOUT
            else:
                # Timed out. Trigger processing to start and block until the next
                # message
                self.processing_required.set()
                timeout = None


def start_worker_process():
    """Called in the parent process to set up the worker. This is not done with the
    Python multiprocessing module because a subprocess made via forking will not work in
    the context of the extension with Nautilus running, and we want to retain Python 2
    compatibility for now so can't use the 'spawn' option for a fresh process. So we
    start a process and set up a connection with it somewhat manually"""
    sock_addr = os.path.join(
        tempfile.gettempdir(), 'git-nautilus-icons-%s' % hexlify(os.urandom(8)).decode()
    )
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(sock_addr)
    sock.listen(1)
    child = Popen([sys.executable, __file__, WORKER_ARG, sock_addr])
    client, _ = sock.accept()
    os.unlink(sock_addr)
    sock.close()
    conn = Connection(os.dup(client.fileno()) if PY2 else client.detach())
    assert conn.recv() == 'hello'
    conn.send('hello')
    return conn, child

def setup_connection_with_parent():
    """Called in the child process to connect to the parent process"""
    sock_addr = sys.argv[1]
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(sock_addr)
    conn = Connection(os.dup(sock.fileno()) if PY2 else sock.detach())
    conn.send('hello')
    assert conn.recv() == 'hello'
    return conn


if WORKER_ARG not in sys.argv:
    # Only define the extension info provider in the parent class
    class InfoProvider(GObject.GObject, Nautilus.InfoProvider):
        INTERVAL = 50
        def __init__(self, *args, **kwargs):
            super(InfoProvider, self).__init__(*args, **kwargs)
            self.timeout_id = None
            self.conn, self.child = start_worker_process()


        def invalidate_directory(self, directory):
            """Invalidate Nautilus's file info for all files in the given directory,
            triggering it to ask us for them again"""
            for path in os.listdir(directory):
                fullpath = os.path.join(directory, path)
                if sys.version_info.major == 2:
                    fullpath = fullpath.encode('utf8')
                uri = pathlib.Path(fullpath).as_uri()
                fileinfo = Nautilus.FileInfo.create_for_uri(uri)
                fileinfo.invalidate_extension_info()

        def update_file_info(self, file):
            filepath = get_filepath(file)
            if filepath is not None:
                # Put it in the pipe for the subprocess to deal with, and ensure the
                # timeout is running to check when the subprocess is done:
                self.conn.send(filepath)
                assert self.conn.recv() == ACK
                if self.timeout_id is None:
                    self.timeout_id = GObject.timeout_add(self.INTERVAL, self.timeout)

        def timeout(self):
            if DEBUG:
                print("parent: timeout")
            self.conn.send(SEND_READY)
            # print("parent: SEND_READY sent, waiting for response")
            files, worker_status = self.conn.recv()
            if DEBUG:
                print("parent: got response:", STATUS[worker_status])
            for filepath, icon in files:
                if DEBUG:
                    print("adding icon for file:", filepath)
                self.set_icon(filepath, icon)
            if worker_status == ALL_DONE:
                GObject.source_remove(self.timeout_id)
                self.timeout_id = None
                return False
            elif worker_status == STILL_WORKING:
                return True
            else:
                raise ValueError(worker_status)

        def set_icon(self, filepath, icon):
            uri = pathlib.Path(filepath).as_uri()
            file = Nautilus.FileInfo.create_for_uri(uri)
            file.add_emblem(icon)
else:
    # We are in the worker process. Start the worker.
    sys.argv.remove(WORKER_ARG)
    conn = setup_connection_with_parent()
    worker = WorkerProcess(conn)
    worker.run()
