#!/usr/bin/env python3
"""Setup script for checkfiles package."""

from setuptools import setup, find_packages

setup(
    name="checkfiles",
    version="0.1.0",
    description="File validation utility for FASTQ and other formats",
    author="CZI",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "boto3",
        "crcmod",
        "scipy>=1.11.0",  # Required for H5AD validation
        "h5py>=3.13.0",   # Required for HDF5/H5AD files
        "scanpy",         # Required for H5AD validation
        "pandas",         # Required for data handling
        "numpy",          # Required for numerical operations
    ],
    entry_points={
        "console_scripts": [
            "checkfiles=src.checkfiles:main",
        ],
    },
)