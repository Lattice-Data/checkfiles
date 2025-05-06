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
        "h5py>=3.1.0",
        "numpy>=1.19.0",
        "scanpy>=1.8.0",
        "anndata>=0.7.8",
        "requests>=2.25.0",
        "boto3>=1.17.0",
        "botocore>=1.20.0",
        "tqdm>=4.60.0",
        "python-magic>=0.4.24",
        "python-magic-bin>=0.4.14; sys_platform == 'win32'",
        "crcmod>=1.7",
    ],
    entry_points={
        "console_scripts": [
            "checkfiles=src.checkfiles:main",
        ],
    },
)