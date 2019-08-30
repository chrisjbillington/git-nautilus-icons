from setuptools import setup

try:
    VERSION = open('version').read().strip()
except FileNotFoundError:
    VERSION = open('../version').read().strip()

setup(
    name='git-caja-icons',
    version=VERSION,
    description="Git status icons for caja",
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='https://github.com/chrisjbillington/git-caja-icons/',
    license="BSD",
    data_files=[
        ('/usr/share/caja-python/extensions', ['git-caja-icons.py']),
    ],
    install_requires=['git-caja-icons-common'],
)
