import os
from setuptools import setup
import glob
from collections import defaultdict

icons = defaultdict(set)
for path in glob.iglob('icons/hicolor/*/*/*'):
    subdir, filename = os.path.split(path)
    icons['share/%s' % subdir].add(path)

extensions = {
    'share/nautilus-python/extensions': ['git-nautilus-icons.py'],
    'share/caja-python/extensions': ['git-nautilus-icons.py'],
    'share/nemo-python/extensions': ['git-nautilus-icons.py'],
}

setup(
    name='git-nautilus-icons',
    use_scm_version=True,
    description="Detailed git status icons for nautilus, nemo, and caja",
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='https://github.com/chrisjbillington/git-nautilus-icons/',
    license="BSD",
    data_files=list(icons.items()) + list(extensions.items()),
)
