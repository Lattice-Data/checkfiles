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
        "boto3>=1.26.0",
        "crcmod>=1.7",
        "requests>=2.28.1",
        "pysam>=0.21.0",
        "scipy>=1.11.0",  # Required for H5AD validation
        "h5py>=3.13.0",   # Required for HDF5/H5AD files
        "scanpy>=1.9.0",  # Required for H5AD validation
        "pandas>=2.0.0",  # Required for data handling
        "numpy>=1.24.0",  # Required for numerical operations
    ],
    entry_points={
        "console_scripts": [
            "checkfiles=src.checkfiles:main",
        ],
    },
)