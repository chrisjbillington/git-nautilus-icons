from PIL import Image

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


for tl, tr, bl, br in all_icons:
    # background_image = None
    background_image = Image.new("RGBA", (24, 24))
    if tl is not None:
        tl_file = 'sub_icons/{}.png'.format(tl)
        tl_image = Image.open(tl_file)
        background_image.paste(tl_image, (0, 0), tl_image)
    if tr is not None:
        tr_file = 'sub_icons/{}.png'.format(tr)
        tr_image = Image.open(tr_file)
        background_image.paste(tr_image, (0, 0), tr_image)
    if bl is not None:
        bl_file = 'sub_icons/{} l.png'.format(bl)
        bl_image = Image.open(bl_file)
        background_image.paste(bl_image, (0, 0), bl_image)
    if br is not None:
        br_file = 'sub_icons/{} r.png'.format(br)
        br_image = Image.open(br_file)
        background_image.paste(br_image, (0, 0), br_image)
    filename = ' '.join([name for name in (tl, tr, bl, br) if name is not None])
    filename = 'hicolor/24x24/emblems/git {}.png'.format(filename)
    background_image.save(filename)


