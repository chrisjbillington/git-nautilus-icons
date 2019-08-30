import os
from setuptools import setup
import glob
from collections import defaultdict

icons_by_install_dir = defaultdict(set)
for path in glob.iglob('icons/hicolor/*/*/*'):
    subdir, filename = os.path.split(path)
    icons_by_install_dir[f'/usr/share/{subdir}'].add(path)

setup(
    name='git-nautilus-icons-common',
    version=open('../version').read().strip(),
    description="Common files for git-nautilus-icons, git-nemo-icons and git-caja-icons",
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='https://github.com/chrisjbillington/git-nautilus-icons/',
    license="BSD",
    data_files=[('/usr/share/git-nautilus-icons-common', ['git-nautilus-icons.py'])]
    + list(icons_by_install_dir.items()),
)
