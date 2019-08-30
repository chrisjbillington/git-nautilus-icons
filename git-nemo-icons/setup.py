from setuptools import setup

try:
    VERSION = open('version').read().strip()
except FileNotFoundError:
    VERSION = open('../version').read().strip()

setup(
    name='git-nemo-icons',
    version=VERSION,
    description="Git status icons for nemo",
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='https://github.com/chrisjbillington/git-nautilus-icons/',
    license="BSD",
    data_files=[
        ('/usr/share/nemo-python/extensions', ['git-nemo-icons.py']),
    ],
    install_requires=['git-nautilus-icons-common'],
)
