from __future__ import print_function, unicode_literals
import sys
import os
import pathlib
import urlparse, urllib
from enum import IntEnum, unique
from gi.repository import Nautilus, GObject
from subprocess import Popen, PIPE, CalledProcessError


ICON_MODE = 'simple' # Set to either 'simple' or 'full'


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


class SimpleIcon(object):
    """Names of gnome icons we use in simple mode, rather than our own
    composite icons"""
    REPO = 'generic'
    CLEAN = 'default'
    UNTRACKED = 'dialog-question'
    ADDED = 'add'
    MODIFIED = 'important'
    RENAMED = 'add'
    DELETED = 'remove'
    UNMERGED = 'error'
    AHEAD = 'up'


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


def get_icon_full(status):
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


def get_icons_simple(status):
    """Returns a list of emblems but makes no distinction between work tree and index"""
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
    icons = []
    if sync_status is SyncStatus.AHEAD:
        icons.append(SimpleIcon.AHEAD)
    if repo_status is RepoStatus.IS_A_REPO:
        icons.append(SimpleIcon.REPO)
    if worktree_status is WorktreeStatus.UNMERGED:
        icons.append(SimpleIcon.UNMERGED)
    elif worktree_status is WorktreeStatus.MODIFIED or index_status is IndexStatus.MODIFIED:
        icons.append(SimpleIcon.MODIFIED)
    elif worktree_status is WorktreeStatus.DELETED or index_status is IndexStatus.DELETED:
        icons.append(SimpleIcon.DELETED)
    elif index_status is IndexStatus.RENAMED:
        icons.append(SimpleIcon.RENAMED)
    elif index_status is IndexStatus.ADDED:
        icons.append(SimpleIcon.ADDED)
    elif worktree_status is WorktreeStatus.UNTRACKED and index_status is IndexStatus.CLEAN:
        # If a folder/repo contains both clean tracked files and untracked, we show both icons:
        icons.append(SimpleIcon.CLEAN)
        icons.append(SimpleIcon.UNTRACKED)
    elif worktree_status is WorktreeStatus.UNTRACKED:
        icons.append(SimpleIcon.UNTRACKED)
    elif worktree_status is WorktreeStatus.CLEAN or index_status is IndexStatus.CLEAN:
        icons.append(SimpleIcon.CLEAN)
    return icons

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
        return stdout.decode('utf8')
    except OSError:
        # Git not installed, or repo path doesn't exist or isn't a directory.
        raise NotARepo()
    else:
        if proc.returncode:
            if 'Not a git repository' in stderr.decode('utf8'):
                raise NotARepo()
            else:
                raise CalledProcessError(proc.returncode, cmd, output=(stdout + stderr))


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


def get_folder_overall_status(path, file_statuses):
    """Returns a 3-tuple of an IndexStatus, WorktreeStatus and MergeStatus,
    chosen based on the most severe of the corresponding statuses of the
    files. File statuses provided need not have only filepaths within the
    folder, this function filters for them itself."""
    filtered_statuses = {stat for name, stat in file_statuses.items()
                         if name.startswith(path + os.path.sep)}
    if filtered_statuses:
        index_statuses, worktree_statuses, merge_statuses = zip(*filtered_statuses)
        index_status = max(index_statuses)
        worktree_status = max(worktree_statuses)
        merge_status = max(merge_statuses)
    else:
        # No files listed. Maybe the directory, or a parent directory are listed:
        index_status, worktree_status, merge_status = file_statuses.get_status(path)
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
    index_status, worktree_status, merge_status = get_folder_overall_status(path, statuses)
    return sync_status, repo_status, index_status, worktree_status, merge_status


def repo_status(path):
    """Return the status of the repo overall as well as a dict of the statuses
    of all non-ignored files in it. All files within the work tree but not
    listed in the output can safely be assumed to have status IGNORED.
    Raises NotARepo if the path no longer points to a git repo."""
    repo_root = get_repo_root(path)
    # 'git status' will get all files other than ignored and unmodified ones:
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
                # A normal folder. Give its overall status:
                status = get_folder_overall_status(fullname, file_statuses)
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
            if sys.version < '3':
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


class InfoProvider(GObject.GObject, Nautilus.InfoProvider):
    def update_file_info(self, file):
        uri = urllib.unquote(file.get_uri()).decode('utf8')
        parsed_uri = urlparse.urlparse(uri)
        if parsed_uri.scheme != 'file':
            return
        filepath = os.path.abspath(os.path.join(parsed_uri.netloc, parsed_uri.path))
        status = Cache.get(filepath)
        if DEBUG:
            print(os.path.basename(filepath))
            if status is not None:
                for s in status:
                    print('   ', s)
        if status is not None:
            if ICON_MODE == 'simple':
                icons = get_icons_simple(status)
                for icon in icons:
                    file.add_emblem(icon)
                    if DEBUG:
                        print('    icon: ', icon)
            elif ICON_MODE == 'full':
                icon = get_icon_full(status)
                if icon is not None:
                    if DEBUG:
                        print('    icon:', icon)
                    file.add_emblem(icon)
            else:
                sys.stderr.write("invalid ICON_MODE {}, must be 'simple' or 'full'\n".format(ICON_MODE))

