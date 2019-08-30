from setuptools import setup

setup(
    name='git-nemo-icons',
    version=open('../version').read().strip(),
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
