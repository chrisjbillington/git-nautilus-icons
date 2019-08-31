#!/usr/bin/bash

set -e

for PACKAGE in git_nautilus_icons_common git_nautilus_icons git_nemo_icons git_caja_icons
do
    cd $PACKAGE
    rm -rf dist
    python setup.py sdist
    twine upload --skip-existing dist/*
    rm -rf dist *.egg-info
    cd ..
done
