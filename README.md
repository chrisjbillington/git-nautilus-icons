# git_nautilus_icons

Use Git? Use nautilus, nemo or caja? Why not have your file browser give you info
about your repos?

`git_nautilus_icons` overlays emblems saying whether files are modified, added,
untracked etc, with a high level of detail showing the exact git status of each file
including both staged and unstaged changes separately. It marks git repos as such and
displays icons on them showing whether they have changed files, unpushed commits, etc.
When using very small icons in nautilus, only icons for unstaged changes are shown, as
the more detailed information would not be visible at such a small size.

## Screenshots

### nautilus

![screenshot-nautilus](screenshot_nautilus.png)

### nemo

![screenshot-nautilus](screenshot_nemo.png)

### caja

![screenshot-nautilus](screenshot_caja.png)


## Installation

Installation instructions or various distros follow. After installation, restart
nautilus/nemo/caja with `killall {nautilus,nemo,caja}`, and then the plugin will be
loaded next time nautilus/nemo/caja is run.

### Debian-based
![debian](distro_icons/debian.png) ![ubuntu](distro_icons/ubuntu.png) ![mint](distro_icons/mint.png) ![pop](distro_icons/pop.png)

In Debian-based distros, install the required dependencies using `apt`, then install the
plugin with `pip`. In the below commands, replace `{nautilus,nemo,caja}` with the
specific file browser you want to install the plugin for.

```bash
sudo apt-get install python-gi python-{nautilus,nemo,caja} python-pathlib python-enum34 python-pip
sudo pip install git_{nautilus,nemo,caja}_icons
# To uninstall, run:
# sudo pip uninstall git_{nautilus,nemo,caja}+icons git_nautilus_icons_common
```

---
**NOTE**

 the required dependencies will change in the future as these distros move to
building nautilus/nemo/caja python plugin support with Python 3 instead of Python 2. If
you are from the future and I have forgotten to update these instructions after this has
occurred, the following should work:

```bash
sudo apt-get install python3-gi python3-{nautilus,nemo,caja} python3-pip
sudo pip3 install git_{nautilus,nemo,caja}_icons
# To uninstall, run:
# sudo pip3 uninstall git_{nautilus,nemo,caja}_icons git_nautilus_icons-common
```
---


### Arch-based

![arch](distro_icons/arch.png) ![manjaro](distro_icons/manjaro.png)

In Arch-based distros, use the AUR packages:

[`git-nautilus-icons`](https://aur.archlinux.org/packages/git-nautilus-icons/)<sup>AUR</sup> or [`git-nautilus-icons-git`](https://aur.archlinux.org/packages/git-nautilus-icons-git/)<sup>AUR</sup>

[`git-nautilus-icons-py2`](https://aur.archlinux.org/packages/git-nautilus-icons-py2/)<sup>AUR</sup> or [`git-nautilus-icons-py2-git`](https://aur.archlinux.org/packages/git-nautilus-icons-py2-git/)<sup>AUR</sup>

[`git-nemo-icons`](https://aur.archlinux.org/packages/git-nemo-icons/)<sup>AUR</sup> or [`git-nemo-icons-git`](https://aur.archlinux.org/packages/git-nemo-icons-git/)<sup>AUR</sup>

[`git-caja-icons-py2`](https://aur.archlinux.org/packages/git-caja-icons-py2/)<sup>AUR</sup> or [`git-caja-icons-git`](https://aur.archlinux.org/packages/git-caja-icons-git/)<sup>AUR</sup>


Note that nautilus on Arch currently supports Python 2 or Python 3 extensions, but not
both at the same time. If you are running other nautilus extensions that require Python
2, you will need to install the `-py2` AUR package. Otherwise, or if in doubt, install
the Python 3 version:
[`git-nautilus-icons`](https://aur.archlinux.org/packages/git-nautilus-icons/)<sup>AUR</sup>.

At present, caja on Arch only supports Python 2 extensions, and nemo only supports
Python 3 extensions. caja will [likely change to
support](https://bugs.archlinux.org/task/62919) Python 3 extensions in the future, at
which point I will make a `git_caja_icons` AUR package. Please file an issue or comment
on the AUR package page to remind me to do this if I forget.

### Other distros
![other](distro_icons/linux.png)

If the version of nautilus, nemo, or caja shipped by your distro supports Python 3
extensions, then install the Python 3 GObject introspection package, possibly named
named `python3-gi` or `python3-gobject`, and the Python 3 extension module for
nautilus/nemo/caja, likely called `python3-{nautilus,nemo,caja}`. Ensure you have the
Python 3 version of `pip` installed, and then run (replacing `{nautilus,nemo,caja}` with
the file browser you want to install the extension for):

```bash
sudo pip3 install git_{nautilus,nemo,caja}_icons
```

Note that on some distros, `python3` is named `python` and `pip3` is named `pip`.
 
If the version of nautilus, nemo, or caja shipped by your distro only supports Python 2
extensions, then you additionally require the Python 2 `pathlib` and `enum34` packages,
likely called `python-pathlib` and `python-enum34`. Then the instructions are the same
as above except with the Python 2 versions of the GObject introspection library, file
browser extension support, and pip.

Make sure you install the extension using the correct version of pip: if you have Python
2 extension support for nautilus, nemo, or caja, you must use pip from Python 2, and if
you have Python 3 extension support then you must use pip from Python 3. You will not
get an error if you install using the wrong pip, but the result will not work.

If you know the required dependencies for your distro, please file an issue or a pull
request for this project and I will update these instructions to include them.

## Icon key

Here is what each possible file status looks like, as well as a few examples of what
repositories may look like. Folders and repositories are marked with the status of their
contents, with the 'worst' status in the index and work tree shown (not necessarily from
the same file). For files deleted from the work tree, their status will only be visible
via their parent directory, so this is how they are shown below. Repos are also marked
with whether or not they are ahead of remote.

![alt tag](key.png)

## Simplified icons at small sizes

---
**NOTE**

This feature does not currently work at the smallest sizes due to there being no way
(that I know of) for an application to add 8x8 and 12x12 icons to the icon theme in a
theme-independent way. I have made a merge reqest to the [hicolor icon
theme](https://gitlab.freedesktop.org/xdg/default-icon-theme/merge_requests/1) that
would resolve the issue. In the meantime, if you want the simplified icons to work at
the smallest sizes, you may use the patched `index.theme` file from that merge request:
```bash
wget https://gitlab.freedesktop.org/chrisjbillington/default-icon-theme/raw/master/index.theme
sudo mv index.theme /usr/share/icons/hicolor/index.theme
```
---

At small file icon sizes (16x16, 24x24, and 32x32), there is not enough room to show detailed
information for each file and simplified icons are shown instead, displaying only the
working tree status of each file, folder, or repository. These icon sizes are only
available in the list/tree view of nautilus. Here is what that looks like for the
smallest icon size in nautilus:

![alt tag](small_icons.png)

## Blacklisting

You can blacklist repositories or directories, to tell `git_nautilus_icons` not to check
git statuses there. This could be useful in the case of an extremely large repository
where calling `git status` is slow and so the extension slows down browsing in nautilus.
Git calls by this extension are asynchronous and so do not cause the file browser to
hang, but nautilus/nemo/caja can be slow to render large numbers of emblems.

To blacklist a repository or directory, add a line containing the full path to the
repository or directory to the file `$HOME/.config/git_nautilus_icons/blacklist.conf`.
Note that the path to this file is the same for all versions of the extension—there are
not separate blacklists for the nemo and caja versions of the extension.
`git-nautilus-icons` will ignore any files in blacklisted directories or any of their
subdirectories.

You will need to kill the file browser with `killall {nautilus,nemo,caja}` after
changing the blacklist, it will take effect when nautilus/nemo/caja is next run.

## Notes

Icons are updated every time you browse to a directory, but whilst in a directory,
nautilus/nemo/caja doesn't ask the extension for new icons unless it sees a file change
on disk. Because of this, statuses may be incorrect after a `git add` or `git commit`.
Press F5 to force a refresh.
