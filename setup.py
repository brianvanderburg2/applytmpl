#!/usr/bin/env python

from setuptools import setup, find_packages

metadata = {}
with open("mrbavii_applytmpl/_version.py") as handle:
    exec(handle.read(), metadata)

setup(
    name="mrbavii_applytmpl",
    version=metadata["__version__"],
    description=metadata["__doc__"].strip(),
    url='',
    author=metadata["__author__"],
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "mrbavii-applytmpl = mrbavii_applytmpl.main:main"
        ]
    }
)
