import os
import pytest
import tempfile
import subprocess
from pathlib import Path


@pytest.fixture(scope="session")
def resources_dir():
    """Return path to test resources directory."""
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def fastq_dir(resources_dir):
    """Return path to FASTQ test data directory."""
    return resources_dir / "fastq"


@pytest.fixture(scope="session")
def h5ad_dir(resources_dir):
    """Return path to H5AD test data directory."""
    # Create directory if it doesn't exist
    h5ad_path = resources_dir / "h5ad"
    h5ad_path.mkdir(exist_ok=True)
    return h5ad_path


@pytest.fixture
def valid_fastq_files(fastq_dir):
    """Return a list of valid FASTQ files."""
    valid_dir = fastq_dir / "valid"
    return list(valid_dir.glob("*.fastq"))


@pytest.fixture
def invalid_fastq_files(fastq_dir):
    """Return a list of invalid FASTQ files."""
    invalid_dir = fastq_dir / "invalid"
    return list(invalid_dir.glob("*.fastq"))


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def run_checkfiles():
    """Fixture to run checkfiles with given arguments and return results."""
    def _run(args, env=None):
        cmd = ["python", "-m", "src.checkfiles"] + args
        result = subprocess.run(
            cmd, 
            env=env or os.environ.copy(),
            capture_output=True,
            text=True
        )
        return result
    return _run 