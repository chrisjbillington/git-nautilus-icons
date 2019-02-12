#####################################################################
#                                                                   #
# Copyright 2016, Chris Billington                                  #
#                                                                   #
# This file is part of the git-nautilus-icons project (see          #
# https://github.com/chrisjbillington/git_nautilus_icons) and is    #
# licensed under the Simplified BSD License. See LICENSE in         #
# the root directory of the project for the full license.           #
#                                                                   #
#####################################################################

import os
import svgutils.transform as sg

unstaged = ['clean', 'modified', 'deleted', 'untracked']
staged = ['modified', 'renamed', 'added', 'deleted']
clean = 'clean'
untracked = 'untracked'
unmerged_modified = 'unmerged modified'
unmerged_deleted = 'unmerged deleted'
unmerged_added = 'unmerged added'
repo = 'repo'
ahead = 'ahead'

# icon tuple format is (top left, top right, bottom left, bottom right)

# Generate a list of unstaged icons:
unstaged_icons = [(None, None, None, unstaged_name) for unstaged_name in unstaged]

# For each one, generate all possible staged icons:
staged_icons = []
for _, _, _, unstaged_name in unstaged_icons:
    staged_icons.extend([None, None, staged_name, unstaged_name] for staged_name in staged)
# We have an 'clean, untracked' icon for when folders/repos are clean and have unmodified files.
# Otherwise it looks silly to see just the unmodified icon for a folder or repo.
staged_icons.append([None, None, clean, untracked])

# Generate a list of possible unmerged icons:
unmerged_icons = [(None, None, unmerged_modified, unmerged_modified),
                  (None, None, unmerged_modified, unmerged_deleted),
                  (None, None, unmerged_deleted, unmerged_modified),
                  (None, None, unmerged_added, unmerged_added)]


# For each of all icons made so far, make an icon for the case where it's a git repo:
repo_icons = [(None, repo, bl, br) for _, _, bl, br in unstaged_icons + staged_icons + unmerged_icons]

# For each git icon, make an icon for the case where it is ahead:
ahead_icons = [(ahead, repo, bl, br) for _, repo, bl, br in repo_icons]

# Put them all together:
all_icons = unstaged_icons + staged_icons + unmerged_icons + repo_icons + ahead_icons

os.system('mkdir -p ./hicolor/scalable/emblems/')
for tl, tr, bl, br in all_icons:
    #create new SVG figure
    background_image = sg.SVGFigure(32, 32)
    if tl is not None:
        tl_file = 'sub_icons/{}.svg'.format(tl)
        tl_image = sg.fromfile(tl_file).getroot()
        background_image.append(tl_image)
    if tr is not None:
        tr_file = 'sub_icons/{}.svg'.format(tr)
        tr_image = sg.fromfile(tr_file).getroot()
        background_image.append(tr_image)
    if bl is not None:
        bl_file = 'sub_icons/{} l.svg'.format(bl)
        bl_image = sg.fromfile(bl_file).getroot()
        background_image.append(bl_image)
    if br is not None:
        br_file = 'sub_icons/{} r.svg'.format(br)
        br_image = sg.fromfile(br_file).getroot()
        background_image.append(br_image)
    filename = '-'.join([name for name in (tl, tr, bl, br) if name is not None])
    filename = 'hicolor/scalable/emblems/git-{}.svg'.format(filename)
    background_image.save(filename)
