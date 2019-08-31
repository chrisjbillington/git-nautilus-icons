from setuptools import setup

VERSION = open('version').read().strip()

setup(
    name='git_nemo_icons',
    version=VERSION,
    description="Git status icons for nemo",
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='https://github.com/chrisjbillington/git_nautilus_icons/',
    license="BSD",
    install_requires=['git_nautilus_icons_common>=%s' % VERSION],
    data_files=[('/usr/share/nemo-python/extensions/', ['git_nemo_icons.py'])],
)
