"""
Setup configuration for dolly-carton.
"""

from setuptools import setup, find_packages

setup(
    name="dolly-carton",
    version="1.0.0",
    description="Pull data from SGID Internal and push to AGOL",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="AGRC",
    url="https://github.com/agrc/dolly-carton",
    py_modules=["dolly", ***REMOVED***],
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "dolly=dolly:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)