#!/usr/bin/bash

set -e

for PACKAGE in git-nautilus-icons-common git-nautilus-icons git-nemo-icons git-caja-icons
do
    cp version $PACKAGE/
    cp README.md $PACKAGE/
    cp LICENSE $PACKAGE/
    cd $PACKAGE
    rm -rf dist
    python setup.py sdist
    twine upload --skip-existing dist/*
    rm -rf dist *.egg-info version LICENSE README.md
    cd ..
done
