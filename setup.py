from setuptools import setup, find_packages
from setuptools_rust import Binding, RustExtension

setup(
    name="checkfiles",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    rust_extensions=[
        RustExtension("fastq_validator", path="rust/Cargo.toml", binding=Binding.PyO3)
    ],
    # rust extensions are not zip safe, just like C-extensions
    zip_safe=False,
    install_requires=[
        # your dependencies here
    ],
    # Include Rust build artifacts
    include_package_data=True,
)