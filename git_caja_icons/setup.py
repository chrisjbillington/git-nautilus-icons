from setuptools import setup

VERSION = open('version').read().strip()

setup(
    name='git_caja_icons',
    version=VERSION,
    description="Git status icons for caja",
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='https://github.com/chrisjbillington/git_nautilus_icons/',
    license="BSD",
    install_requires=['git_nautilus_icons_common>=%s' % VERSION],
    data_files=[('/usr/share/caja-python/extensions/', ['git_caja_icons.py'])],
)
