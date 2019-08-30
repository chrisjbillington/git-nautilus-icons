from setuptools import setup

setup(
    name='git-nautilus-icons',
    version=open('../version').read().strip(),
    description="Git status icons for nautilus",
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='https://github.com/chrisjbillington/git-nautilus-icons/',
    license="BSD",
    data_files=[
        ('/usr/share/nautilus-python/extensions', ['git-nautilus-icons.py']),
    ],
    install_requires=['git-nautilus-icons-common'],
)
