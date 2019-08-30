import os
from setuptools import setup
from setuptools.command.install import install
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


class Install(install):
    def run(self):
        install.run(self)
        # Symlink to make @2 versions of 16x16 icons:
        os.system('mkdir -p /usr/share/icons/hicolor/16x16@2/emblems/')
        for path in icons_by_install_dir['/usr/share/hicolor/16x16/emblems']:
            os.symlink(
                '/usr/share/%s' % path,
                'usr/share/%s' % path.replace('16x16', '16x16@2'),
            )

setup(
    name='git-nautilus-icons-common',
    version=VERSION,
    description="Common files for git-nautilus-icons, git-nemo-icons and git-caja-icons",
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='https://github.com/chrisjbillington/git-nautilus-icons/',
    license="BSD",
    data_files=[('/usr/share/git-nautilus-icons-common', ['git-nautilus-icons.py'])]
    + list(icons_by_install_dir.items()),
    cmdclass={'install': Install},
)
