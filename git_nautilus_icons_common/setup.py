import os
from setuptools import setup
import glob
from collections import defaultdict

icons_by_install_dir = defaultdict(set)
for path in glob.iglob('icons/hicolor/*/*/*'):
    subdir, filename = os.path.split(path)
    icons_by_install_dir['/usr/share/%s' % subdir].add(path)

try:
    VERSION = open('version').read().strip()
except FileNotFoundError:
    VERSION = open('../version').read().strip()

setup(
    name='git_nautilus_icons_common',
    version=VERSION,
    description="Common files for git_nautilus_icons, git_nemo_icons and git_caja_icons",
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='https://github.com/chrisjbillington/git_nautilus_icons/',
    license="BSD",
    packages=['git_nautilus_icons_common'],
    data_files=list(icons_by_install_dir.items()),
)
