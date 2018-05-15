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
import gi
from gi.repository import GObject
if sys.argv[0] == 'nemo':
    gi.require_version('Nemo', '3.0')
    from gi.repository import Nemo as Nautilus
elif sys.argv[0] == 'caja':
    gi.require_version('Caja', '2.0')
    from gi.repository import Caja as Nautilus
else:
    from gi.repository import Nautilus
from subprocess import Popen, PIPE, CalledProcessError
from collections import defaultdict


# Below is a blacklist for repos that should be ignored. Useful for ignoring
# massive repos that make nautilus run slow. Ensure you don't have a trailing
# slash on the directory paths entered here:

blacklist = ['/home/chrisjbillington/clones/example_repo.git',
             '/home/chrisjbillington/clones/some_other_example_huge_repo.git',
             ]


# Change to print debug information when running Nautilus from the terminal:
DEBUG = False


def blacklisted(path):
    path += '/'
    if any(path.startswith(s + '/') for s in blacklist):
        if DEBUG:
            print('path is blacklisted:', path)
        return True
    return False


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
                'ERROR': (IndexStatus.ERROR, WorktreeStatus.ERROR, MergeStatus.ERROR)}


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


# class InotifyWatcher(object):
#     """A class to watch repos with inotify"""

#     WATCH_flags = (flags.MODIFY | flags.MOVED_FROM | flags.MOVED_TO |
#                    flags.CREATE | flags.DELETE | flags.DELETE_SELF | flags.MOVE_SELF |
#                    flags.ONLYDIR | flags.DONT_FOLLOW | flags.EXCL_UNLINK)

#     def __init__(self):
#         # Repos that we are monitoring:
#         self.repos = set()

#         # Mapping of directories we are watching to the set of (possibly
#         # multiple) repos that they are in:
#         self.dir_to_repos = {}

#         # Mapping of watched directories to a set of thier child directories:
#         self.child_dirs = {}

#         # Mapping of watched directories to their parent directories:
#         self.parent_dirs = {}

#         # Mapping of watch descriptors to directories:
#         self.watch_descriptor_to_dir = {}

#         # Mapping of directories to watch descriptors:
#         self.dir_to_watch_descriptor = {}

#         from inotify_simple import INotify
#         self.inotify = INotify()

#     def fileno(self):
#         return self.inotify.fd

#     def watch_tree(self, path, repo_paths):
#         """Watch all directories in the tree rooted at path and in the given
#         repositories (a set, possibly with more than one repository if the
#         path is in a submodule)"""
#         # Because we initiate watching from the top down, we won't miss any
#         # folders - Those created after we traverse a directory will have
#         # events generated about their creation. We may however see events
#         # about some directories we are already watching. This is no problem,
#         # as adding an identical watch twice has no effect.
#         for dirpath, dirnames, _ in os.walk(path):
#             try:
#                 watch_descriptor = self.inotify.add_watch(dirpath, self.WATCH_flags)
#             except OSError as e:
#                 import errno
#                 if e.errno in (errno.ENOTDIR, errno.ENOENT):
#                     # directory has since been deleted or replaced by a file,
#                     # so we no longer care about it.
#                     pass
#                 else:
#                     raise
#             else:
#                 child_names = [os.path.join(dirpath, d) for d in dirnames]
#                 self.child_dirs[dirpath] = set(child_names)
#                 self.parent_dirs[dirpath] = os.path.dirname(dirpath)

#                 self.dir_to_watch_descriptor[dirpath] = watch_descriptor
#                 self.watch_descriptor_to_dir[watch_descriptor] = dirpath
#                 repos_for_this_dir = self.dir_to_repos.setdefault(dirpath, set())
#                 repos_for_this_dir.update(repo_paths)

#     def rm_watch_tree(self, path):
#         to_remove = [path]
#         while to_remove:
#             path = to_remove.pop()
#             # Remove everything:
#             wd = self.dir_to_watch_descriptor.pop(path)
#             self.inotify.rm_watch(wd)
#             if path in self.repos:
#                 self.repos.remove(path)
#             del self.parent_dirs[path]
#             del self.dir_to_repos[path]
#             del self.watch_descriptor_to_dir[wd]
#             child_dirs = self.child_dirs.pop(path)
#             # And remove all children too:
#             for child_dir in child_dirs:
#                 to_remove.extend(self.dir_to_watch_descriptor[child_dir])

#     def add_repo(self, path):
#         """Start watching a repo"""
#         print('[SUB] add_repo:', os.path.basename(path))
#         self.watch_tree(path, repo_paths=set((path,)))
#         self.repos.add(path)

#     def process_events(self):
#         events = self.inotify.read()
#         update_status_dirs = set()
#         for event in events:
#             if event.mask & flags.IGNORED:
#                 continue
#             path = self.watch_descriptor_to_dir[event.wd]
#             if path.endswith('/.git') and event.name == 'index.lock':
#                 continue
#             print('[SUB]', event)
#             for flag in flags.from_mask(event.mask):
#                 print('[SUB]   ', flag)
#             if event.mask & flags.ISDIR:
#                 subdir_path = os.path.join(path, event.name)
#                 update_status_dirs.add(path)
#                 if event.mask & (flags.DELETE | flags.MOVED_FROM):
#                     # Directory gone, stop watching it:
#                     self.rm_watch_tree(subdir_path)
#                 if event.mask & (flags.CREATE | flags.MOVED_TO):
#                     # New directory, start watching it. Need parent dir to
#                     # know which repo(s) the new dir is in, should be the
#                     # same as its parent dir:
#                     repo_paths = self.dir_to_repos[path]
#                     self.watch_tree(subdir_path, repo_paths)
#             elif event.mask & (flags.MOVE_SELF | flags.DELETE_SELF):
#                 # Directory gone, stop watching it:
#                 self.rm_watch_tree(path)
#             elif event.mask & (flags.CREATE | flags.DELETE | flags.MODIFY |
#                                flags.MOVED_FROM | flags.MOVED_TO):
#                 # Contents of directory changed, so repo status needs updating:
#                 update_status_dirs.add(path)
#             else:
#                 raise ValueError(flags.from_mask(event.mask))

#         # And we have repos to update, if they haven't been removed by
#         # rm_watch_tree:
#         repos_to_update = set()
#         for path in update_status_dirs:
#             try:
#                 repos = self.dir_to_repos[path]
#             except KeyError:
#                 pass # Deleted by another event.
#             else:
#                 repos_to_update.update(repos)

#         return repos_to_update


# class InotifyInformer(object):
#     """A class to let us know if files have changed in a repo since we last
#     asked. We only call 'git status' if they have.'"""
#     ARRAY_SIZE = 1000
#     def __init__(self):
#         from multiprocessing import Pipe, RawArray, Process
#         # We're making a shared array of bytes, and will spawn a subprocess.
#         # The subprocess will write ones to the array for filepaths of repos
#         # that require updating. We will read these and know if repos need
#         # updating, and will write zeros before we do each update so we won't
#         # update again until the subprocess says so by writing another one. We
#         # store which filepath corresponds to which array index (and vice
#         # versa) in dictionaries, and will only store ARRAY_SIZE of them
#         # before going back to the start and overwriting old ones.

#         self.array = RawArray('b', self.ARRAY_SIZE)
#         self.current_index = 0

#         # Bidirectional table so lookups both ways can be fast:
#         self.index_to_filepath = {}
#         self.filepath_to_index = {}

#         self.connection, child_connection = Pipe()

#         self.subproc = Process(target=self.checker, args=(child_connection,))
#         self.subproc.daemon=True
#         self.subproc.start()

#     def requires_update(self, filepath):
#         try:
#             index = self.filepath_to_index[filepath]
#         except KeyError:
#             # We haven't seen this file before. Tell the subprocess about it,
#             # and store it in our dictionaries:
#             self.connection.send(('add', filepath))
#             self._new_file(filepath)
#             self.connection.recv()
#             index = self.current_index
#         if not self.array[index]:
#             return False
#         self.array[index] = 0
#         return True

#     def _new_file(self, filepath):
#         """Called in both processes to update their copies of the data
#         structures when we get a new filepath"""
#         # Store the new filepath in our dictionaries at the current index,
#         # overwriting an old entry if there is one there already:
#         self.current_index = (self.current_index + 1) % self.ARRAY_SIZE
#         existing_filepath = self.index_to_filepath.get(self.current_index, None)
#         if existing_filepath is not None:
#             del self.filepath_to_index[existing_filepath]
#         self.index_to_filepath[self.current_index] = filepath
#         self.filepath_to_index[filepath] = self.current_index

#     def checker(self, connection):
#         import select
#         watcher = InotifyWatcher()
#         while True:
#             (events,[],[]) = select.select([connection, watcher],[],[])
#             if connection in events:
#                 cmd, filepath = connection.recv()
#                 if cmd == 'add':
#                     self._new_file(filepath)
#                     watcher.add_repo(filepath)
#                     self.array[self.current_index] = 1
#                 elif cmd == 'remove':
#                     raise NotImplementedError
#                 connection.send(None)
#             if watcher in events:
#                 repos_to_update = watcher.process_events()
#                 for repo in repos_to_update:
#                     print('[SUB] update detected:', os.path.basename(repo))
#                     index = self.filepath_to_index[repo]
#                     self.array[index] = 1


def example_statuses(path):
    return {os.path.join(path, name): value for name, value in EXAMPLE_FILE_STATUSES.items()}


def get_icon(status):
    if len(status) == 3:
        # It's a file
        index_status, worktree_status, merge_status = status
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
            sub_icons.append('unmerged modified')
            sub_icons.append('unmerged deleted')
        elif merge_status is MergeStatus.WE_DELETED:
            sub_icons.append('unmerged deleted')
            sub_icons.append('unmerged modified')
        elif merge_status is MergeStatus.BOTH_ADDED:
            sub_icons.append('unmerged added')
            sub_icons.append('unmerged added')
        elif merge_status is MergeStatus.BOTH_MODIFIED:
            sub_icons.append('unmerged modified')
            sub_icons.append('unmerged modified')
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
    return 'git ' + ' '.join(sub_icons)


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
            while i < 1000: # Really make sure we don't infinitely loop here if I've made a mistake
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
            else:
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
        raise NotARepo(proc.returncode, cmd, output=(stdout + stderr))
    else:
        if proc.returncode:
            if 'not a git repository' in stderr.decode('utf8').lower():
                raise NotARepo(proc.returncode, cmd, output=(stdout + stderr))
            else:
                raise CalledProcessError(proc.returncode, cmd, output=(stdout + stderr))
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
    index_status, worktree_status, merge_status = get_folder_overall_status(path, set(statuses.values()), statuses)
    return sync_status, repo_status, index_status, worktree_status, merge_status


def repo_status(path):
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
        status_command
    # And now to get all the unmodified files:
    lstree_command = ['git', 'ls-tree', '--full-tree', '-zr', '--name-only', 'HEAD']
    try:
        lstree_output = git_call(lstree_command, path)
    except CalledProcessError as e:
        if not 'Not a valid object name HEAD' in e.output:
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


# import bprofile
# @bprofile.BProfile('test.png')
def directory_status(path):
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
        for basename in os.listdir(path):
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
        # As as optimisation, collect the set of statuses in each directory at
        # the current level we're at:
        statuses_by_dir = get_statuses_by_dir(path, file_statuses)
        for basename in os.listdir(path):
            fullname = os.path.join(path, basename)
            if basename == '.git':
                status = None
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
                status = get_folder_overall_status(fullname, statuses_by_dir[fullname], file_statuses)
            statuses[fullname] = status
    return statuses


class Cache(object):
    file_statuses = {}

    @classmethod
    def update(cls, directory):
        cls.file_statuses = directory_status(directory)
        # Invalidate Nautilus's file info for all files in this directory,
        # triggering it to ask as for them again:
        for path in os.listdir(directory):
            fullpath = os.path.join(directory, path)
            if sys.version_info.major == 2:
                fullpath = fullpath.encode('utf8')
            uri = pathlib.Path(fullpath).as_uri()
            fileinfo = Nautilus.FileInfo.create_for_uri(uri)
            fileinfo.invalidate_extension_info()


    @classmethod
    def get(cls, path):
        if path not in cls.file_statuses:
            cls.update(os.path.dirname(path))
        # We pop to force an update if Nautilus asks for the same file twice -
        # it usually only does so if a file has changed or a refresh has been
        # done or such, so it's appropraite to refresh our cache:
        return cls.file_statuses.pop(path)


def get_filepath(file):
    """Extract filepath from the URI in a NautilusVFSFile object. Return the
    filepath or None if uri scheme is not 'file'"""
    if sys.version_info.major == 2:
        from urlparse import urlparse
        from urllib import unquote
    else:
        from urllib.parse import urlparse
        from urllib.parse import unquote

    parsed_uri = urlparse(file.get_uri())
    if parsed_uri.scheme == 'file':
        netloc = parsed_uri.netloc.decode('utf8')
        path = unquote(parsed_uri.path).decode('utf8')
        return os.path.abspath(os.path.join(netloc, path))

class InfoProvider(GObject.GObject, Nautilus.InfoProvider):
    def update_file_info(self, file):
        filepath = get_filepath(file)
        if filepath is None:
            return
        status = Cache.get(filepath)
        if DEBUG:
            print(os.path.basename(filepath))
            if status is not None:
                for s in status:
                    print('   ', s)
        if status is not None:
            icon = get_icon(status)
            if icon is not None:
                if DEBUG:
                    print('    icon:', icon)
                file.add_emblem(icon)
