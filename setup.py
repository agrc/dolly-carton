#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
setup.py
A module that installs dolly-carton as a module
"""

from pathlib import Path

from setuptools import find_packages, setup

setup(
    name="dolly-carton",
    version="1.0.4",
    license="MIT",
    description="Project description.",
    long_description=(Path(__file__).parent / "README.md").read_text(),
    long_description_content_type="text/markdown",
    author="UGRC",
    author_email="ugrc-developers@utah.gov",
    url="https://github.com/agrc/dolly-carton",
    packages=find_packages("src"),
    package_dir={"": "src"},
    package_data={
        "dolly": ["dev_mocks.json"],
    },
    include_package_data=True,
    zip_safe=True,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Topic :: Utilities",
    ],
    project_urls={
        "Issue Tracker": "https://github.com/agrc/dolly-carton/issues",
    },
    keywords=["gis"],
    install_requires=[
        "arcgis==2.*",
        "google-cloud-firestore==2.*",
        "humanize==4.*",
        "pyodbc==5.*",
        "requests==2.*",
        "typer==0.*",
    ],
    extras_require={
        "tests": [
            "pytest-cov==6.*",
            "pytest-instafail==0.5.*",
            "pytest-mock==3.*",
            "pytest-watch==4.*",
            "pytest==8.*",
            "ruff==0.*",
        ],
    },
    setup_requires=[
        "pytest-runner",
    ],
    entry_points={
        "console_scripts": [
            "dolly=dolly.main:cli",
            "dolly-cleanup-dev-agol=dolly.main:cleanup_dev_agol_items",
        ]
    },
)
