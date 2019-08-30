import os
from setuptools import setup
from setuptools.command.install import install

try:
    VERSION = open('version').read().strip()
except FileNotFoundError:
    VERSION = open('../version').read().strip()

class Install(install):
    def run(self):
        install.run(self)
        os.system('mkdir -p /usr/share/nemo-python/extensions/')
        os.symlink(
            '/usr/share/git-nautilus-icons-common/git-nautilus-icons.py',
            '/usr/share/nemo-python/extensions/git-nemo-icons.py',
        )

setup(
    name='git-nemo-icons',
    version=VERSION,
    description="Git status icons for nemo",
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='https://github.com/chrisjbillington/git-nemo-icons/',
    license="BSD",
    install_requires=['git-nautilus-icons-common'],
    cmdclass={'install': Install},
)
