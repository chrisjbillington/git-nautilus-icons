from __future__ import print_function, unicode_literals
import sys
import os
import pathlib
import urlparse, urllib
from enum import IntEnum, unique
from gi.repository import Nautilus, GObject
from subprocess import Popen, PIPE, CalledProcessError


# Below is a blacklist for repos that should be ignored. Useful for ignoring
# massive repos at least until I write a version of this plugin that doesn't
# make as many redundant 'git status' calls. Git's pretty fast though, so I
# haven't noticed any problems with repos I've been working with. Nautilus
# being slow to display the icons after we tell it which ones to use is the
# slowest bit so far! I even plan to fix that by remembering what we told it
# last time and not telling it again unless it's changed.

# Anyway if you have some really huge repos that are slow to browse because of
# this extension, put their absolute paths here:
BLACKLIST = ['/home/bilbo/clones/example_repo.git',
             '/home/bilbo/clones/some_other_example_huge_repo.git']


@unique
class RepoStatus(IntEnum):
    """Possible statuses for a repository, ordered by severity."""
    NOT_A_REPO = 0
    CLEAN = 1
    AHEAD = 2
    HAS_UNTRACKED = 3
    HAS_ADDED = 4
    HAS_DELETED = 5
    HAS_MODIFIED = 6
    HAS_UNMERGED = 7


@unique
class FolderStatus(IntEnum):
    """Possible statuses for a folder, ordered by severity."""
    HAS_UNMODIFIED = 1
    HAS_UNTRACKED = 2
    HAS_ADDED = 3
    HAS_DELETED = 4
    HAS_MODIFIED = 5
    HAS_UNMERGED = 6


@unique
class FileStatus(IntEnum):
    """Possible statuses for a file, ordered by severity."""
    NOT_IN_REPO = 0
    GIT_HIDDENDIR = 1
    IGNORED = 2
    UNMODIFIED = 3
    UNTRACKED = 4
    ADDED = 5
    DELETED = 6
    MODIFIED = 7
    UNMERGED = 8


class IconName(object):
    """Mapping of statuses to icon names"""
    GIT_HIDDENDIR = None
    REPO = 'generic'
    IGNORED = None
    UNMODIFIED = 'default'
    UNTRACKED = 'dialog-question'
    ADDED = 'add'
    MODIFIED = 'important'
    DELETED = 'remove'
    UNMERGED = 'error'
    AHEAD = 'up'


repo_icon_mapping = {RepoStatus.NOT_A_REPO: None,
                     RepoStatus.CLEAN: IconName.UNMODIFIED,
                     RepoStatus.HAS_UNTRACKED: IconName.UNTRACKED,
                     RepoStatus.AHEAD: IconName.AHEAD,
                     RepoStatus.HAS_ADDED: IconName.ADDED,
                     RepoStatus.HAS_DELETED: IconName.DELETED,
                     RepoStatus.HAS_MODIFIED: IconName.MODIFIED,
                     RepoStatus.HAS_UNMERGED: IconName.UNMERGED}


folder_icon_mapping = {FolderStatus.HAS_UNMODIFIED: IconName.UNMODIFIED,
                       FolderStatus.HAS_UNTRACKED: IconName.UNTRACKED,
                       FolderStatus.HAS_ADDED: IconName.ADDED,
                       FolderStatus.HAS_DELETED: IconName.DELETED,
                       FolderStatus.HAS_MODIFIED: IconName.MODIFIED,
                       FolderStatus.HAS_UNMERGED: IconName.UNMERGED}


file_icon_mapping = {FileStatus.NOT_IN_REPO: None,
                     FileStatus.GIT_HIDDENDIR: IconName.GIT_HIDDENDIR,
                     FileStatus.IGNORED: IconName.IGNORED,
                     FileStatus.UNMODIFIED: IconName.UNMODIFIED,
                     FileStatus.UNTRACKED: IconName.UNTRACKED,
                     FileStatus.ADDED: IconName.ADDED,
                     FileStatus.MODIFIED: IconName.MODIFIED,
                     # We don't expect to encounter deleted files, but the
                     # folders and repos they were deleted from them may show
                     # the icon:
                     FileStatus.DELETED: IconName.DELETED,
                     FileStatus.UNMERGED: IconName.UNMERGED}


STATUS_CODES = {' M': FileStatus.MODIFIED,
                'MM': FileStatus.MODIFIED,
                'AM': FileStatus.MODIFIED,
                'DM': FileStatus.MODIFIED,
                'RM': FileStatus.MODIFIED,
                'CM': FileStatus.MODIFIED,
                'M ': FileStatus.MODIFIED,
                'R ': FileStatus.MODIFIED,
                'C ': FileStatus.MODIFIED,
                'A ': FileStatus.ADDED,
                'D ': FileStatus.DELETED,
                ' D': FileStatus.DELETED,
                'MD': FileStatus.DELETED,
                'AD': FileStatus.DELETED,
                'RD': FileStatus.DELETED,
                'CD': FileStatus.DELETED,
                'DD': FileStatus.UNMERGED,
                'AU': FileStatus.UNMERGED,
                'UD': FileStatus.UNMERGED,
                'UA': FileStatus.UNMERGED,
                'DU': FileStatus.UNMERGED,
                'AA': FileStatus.UNMERGED,
                'UU': FileStatus.UNMERGED,
                '??': FileStatus.UNTRACKED,
                '!!': FileStatus.IGNORED}


class NotARepo(CalledProcessError):
    pass


class RepoStatusSet(set):
    pass


class FolderStatusSet(set):
    pass


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
    return os.path.isdir(os.path.join(path, '.git'))


def is_in_work_tree(path):
    """returns whether a path is in the work tree of a git repo (ie, not
    inside .git!)"""
    if os.path.abspath(path) in BLACKLIST:
        return False
    cmd = ['git', 'rev-parse', '--is-inside-work-tree']
    try:
        return git_call(cmd, path).strip() == 'true'
    except NotARepo:
        return False


def get_repo_root(path):
    """Returns the root directory of a repo, given a directory within it,
    or raises NotARepo if the directory is not in a git repo"""
    cmd = ['git', 'rev-parse', '--git-dir']
    output = git_call(cmd, path).strip()
    if output == '.git':
        return path
    else:
        # Otherwise it's given as an absolute path:
        return os.path.dirname(output)


def repo_has_unpushed_commits(path):
    """Returns whether the repo at a given path has any unpushed commits"""
    cmd = ['git', 'for-each-ref', '--format="%(push:track)"', 'refs/heads']
    return 'ahead' in git_call(cmd, path)


def get_repo_overall_status(path, statuses):
    """Returns a subset of possible statuses for a repo. Output always
    includes AHEAD if the repo has unpushed changes in any branch, and
    includes only the most severe of CLEAN, HAS_UNTRACKED, HAS_MODIFIED and
    HAS_UNMERGED.
    """
    overall_status = RepoStatusSet()
    most_severe_status = max(statuses.values()) if statuses else FileStatus.IGNORED
    if most_severe_status in (FileStatus.IGNORED, FileStatus.UNMODIFIED):
        overall_status.add(RepoStatus.CLEAN)
    elif most_severe_status is FileStatus.UNTRACKED:
        overall_status.add(RepoStatus.HAS_UNTRACKED)
    elif most_severe_status is FileStatus.ADDED:
        overall_status.add(RepoStatus.HAS_ADDED)
    elif most_severe_status is FileStatus.DELETED:
        overall_status.add(RepoStatus.HAS_DELETED)
    elif most_severe_status is FileStatus.MODIFIED:
        overall_status.add(RepoStatus.HAS_MODIFIED)
    elif most_severe_status is FileStatus.UNMERGED:
        overall_status.add(RepoStatus.HAS_UNMERGED)
    else:
        raise ValueError(most_severe_status)

    if repo_has_unpushed_commits(path):
        overall_status.add(RepoStatus.AHEAD)

    return overall_status


def get_folder_overall_status(path, statuses):
    """Returns a subset of possible statuses for a folder containing files
    with given statuses. statuses need not have only filepaths within the
    folder, this function filters for them itself. Returns the most severe
    status of (HAS_UNMODIFIED, HAS_ADDED, HAS_DELETED,
    HAS_MODIFIED and HAS_UNMERGED), as well as HAS_UNTRACKED if relevant.
    """
    filtered_statuses = {stat for name, stat in statuses.items()
                         if name.startswith(path + os.path.sep)}

    overall_status = FolderStatusSet()
    if FileStatus.UNTRACKED in filtered_statuses:
        overall_status.add(FolderStatus.HAS_UNTRACKED)

    if FileStatus.UNMERGED in filtered_statuses:
        overall_status.add(FolderStatus.HAS_UNMERGED)
    elif FileStatus.MODIFIED in filtered_statuses:
        overall_status.add(FolderStatus.HAS_MODIFIED)
    elif FileStatus.DELETED in filtered_statuses:
        overall_status.add(FolderStatus.HAS_DELETED)
    elif FileStatus.ADDED in filtered_statuses:
        overall_status.add(FolderStatus.HAS_ADDED)
    elif FileStatus.UNMODIFIED in filtered_statuses:
        overall_status.add(FolderStatus.HAS_UNMODIFIED)
    return overall_status


def repo_status(path):
    """Return the status of the repo overall as well as a dict of the statuses
    of all files in it. Or if the path is not a git repo, return
    Repo.NOT_A_REPO and an empty dict. If the path is indeed a git repo, then
    all files (other than those in .git) within the tree not listed can safely
    be assumed to have status File.IGNORED."""
    if not is_in_work_tree(path):
        return RepoStatus.NOT_A_REPO, {}
    repo_root = get_repo_root(path)
    # 'git status' will get all files other than unmodified ones:
    status_command = ['git', 'status', '--ignored', '-z']
    status_output = git_call(status_command, path)
    statuses = {}
    status_entries = status_output.split('\x00')[:-1]
    i = 0
    while i < len(status_entries):
        status_entry = status_entries[i]
        status = status_entry[0:2]
        relpath = status_entry[3:]
        filename = os.path.join(repo_root, relpath)
        statuses[filename] = STATUS_CODES[status]
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
                statuses[filename] = FileStatus.UNMODIFIED
    overall_status = get_repo_overall_status(path, statuses)
    return overall_status, statuses


def directory_status(path):
    """Returns the statuses for all the files/directories in a given path
    (without recursing). For directories in a repo, their status is given as
    the most severe of their contents. For repositories, their status is given
    as their overall status. For submodules, their overall status is given,
    but is calculated as if the repo contained a file with the status of the
    submodule itself. Thus, if a submodule is itself clean, but is checked out
    at a different commit than recorded by a commit in the parent repo, then
    it will appear as Repo.HAS_MODIFIED."""
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
                status = FileStatus.NOT_IN_REPO
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
                status = FileStatus.GIT_HIDDENDIR
            elif not os.path.isdir(fullname):
                # A normal file:
                status = file_statuses.get(fullname, FileStatus.IGNORED)
            elif is_git_repo(fullname):
                # A submodule. Give its overall status, calculated as if it
                # contained a file with its own status in the parent repo.
                # This ensures the most severe of the subrepo's own status and
                # its status in the parent repo will be shown.
                file_status = file_statuses.get(fullname, FileStatus.UNMODIFIED)
                try:
                    _, subrepo_file_statuses = repo_status(fullname)
                except NotARepo:
                    # subrepo deleted
                    continue
                subrepo_file_statuses.update({fullname: file_status})
                status = get_repo_overall_status(fullname, subrepo_file_statuses)
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
        if isinstance(status, RepoStatusSet):
            file.add_emblem(IconName.REPO)
            for individual_status in status:
                icon_name = repo_icon_mapping[individual_status]
                if icon_name is not None:
                    file.add_emblem(icon_name)
        elif isinstance(status, FolderStatusSet):
            for individual_status in status:
                icon_name = folder_icon_mapping[individual_status]
                if icon_name is not None:
                    file.add_emblem(icon_name)
        else:
            icon_name = file_icon_mapping[status]
            if icon_name is not None:
                file.add_emblem(icon_name)





