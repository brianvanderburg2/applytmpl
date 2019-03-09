#!/usr/bin/env python3

from setuptools import setup, find_namespace_packages

metadata = {}
with open("mrbavii/applytmpl/_version.py") as handle:
    exec(handle.read(), metadata)

setup(
    name="mrbavii.applytmpl",
    version=metadata["__version__"],
    description=metadata["__doc__"].strip(),
    url='',
    author=metadata["__author__"],
    packages=find_namespace_packages(),
    entry_points={
        "console_scripts": [
            "mrbavii-applytmpl = mrbavii.applytmpl.run:run"
        ]
    }
)
