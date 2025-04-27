#!/bin/bash
# Script to verify that samtools is properly installed in the Docker container

set -e

echo "Building Docker image..."
docker build -t checkfiles-test -f docker/Dockerfile .

echo "Verifying samtools installation in Docker container..."
docker run --rm checkfiles-test bash -c "samtools --version"

echo "Testing BAM validator in Docker container..."
docker run --rm -v "$(pwd)/src/tests/data/bam/valid:/data" checkfiles-test bash -c "python -c \"
from src.validators.bam import BamValidator
validator = BamValidator()
result = validator.validate_file('/data/small.bam')
print('BAM validation result:', result['valid'])
\""

echo "Testing CRAM validator in Docker container..."
docker run --rm -v "$(pwd)/src/tests/data/cram/valid:/data" checkfiles-test bash -c "python -c \"
from src.validators.cram import CramValidator
validator = CramValidator()
result = validator.validate_file('/data/small.cram')
print('CRAM validation result:', result['valid'])
\""

echo "Docker integration verification complete." 