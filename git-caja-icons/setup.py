from setuptools import setup

setup(
    name='git-caja-icons',
    version=open('../version').read().strip(),
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
