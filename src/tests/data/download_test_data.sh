#!/bin/bash
# Script to download sample BAM and CRAM files for testing

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BAM_VALID_DIR="${SCRIPT_DIR}/bam/valid"
BAM_INVALID_DIR="${SCRIPT_DIR}/bam/invalid"
CRAM_VALID_DIR="${SCRIPT_DIR}/cram/valid"
CRAM_INVALID_DIR="${SCRIPT_DIR}/cram/invalid"

# Ensure directories exist
mkdir -p "${BAM_VALID_DIR}" "${BAM_INVALID_DIR}" "${CRAM_VALID_DIR}" "${CRAM_INVALID_DIR}"

echo "Downloading sample BAM files..."

# Download a small valid BAM file from ENA
if [ ! -f "${BAM_VALID_DIR}/small.bam" ]; then
    curl -L "https://ftp.sra.ebi.ac.uk/vol1/run/ERR164/ERR1641394/ENCFF000LAM.bam" \
        -o "${BAM_VALID_DIR}/small.bam"
    echo "Downloaded valid BAM file"
fi

# Create an invalid BAM file (corrupted header)
if [ ! -f "${BAM_INVALID_DIR}/corrupted_header.bam" ]; then
    # First copy the valid BAM
    cp "${BAM_VALID_DIR}/small.bam" "${BAM_INVALID_DIR}/corrupted_header.bam"
    # Then corrupt the header (replace first few bytes with random data)
    dd if=/dev/urandom of="${BAM_INVALID_DIR}/corrupted_header.bam" bs=1 count=10 conv=notrunc
    echo "Created corrupted header BAM file"
fi

# Create an invalid BAM file (truncated)
if [ ! -f "${BAM_INVALID_DIR}/truncated.bam" ]; then
    # Copy just the first 1000 bytes of the valid BAM
    dd if="${BAM_VALID_DIR}/small.bam" of="${BAM_INVALID_DIR}/truncated.bam" bs=1000 count=1
    echo "Created truncated BAM file"
fi

echo "Downloading sample CRAM files..."

# Download a small valid CRAM file
if [ ! -f "${CRAM_VALID_DIR}/small.cram" ]; then
    curl -L "https://ftp.sra.ebi.ac.uk/vol1/run/ERR324/ERR3242499/NA12878.alt_bwamem_GRCh38DH.20150706.CEU.exome.cram" \
        -o "${CRAM_VALID_DIR}/small.cram"
    echo "Downloaded valid CRAM file"
fi

# Create an invalid CRAM file (corrupted header)
if [ ! -f "${CRAM_INVALID_DIR}/corrupted_header.cram" ]; then
    # First copy the valid CRAM
    cp "${CRAM_VALID_DIR}/small.cram" "${CRAM_INVALID_DIR}/corrupted_header.cram"
    # Then corrupt the header (replace first few bytes with random data)
    dd if=/dev/urandom of="${CRAM_INVALID_DIR}/corrupted_header.cram" bs=1 count=10 conv=notrunc
    echo "Created corrupted header CRAM file"
fi

# Create an invalid CRAM file (truncated)
if [ ! -f "${CRAM_INVALID_DIR}/truncated.cram" ]; then
    # Copy just the first 1000 bytes of the valid CRAM
    dd if="${CRAM_VALID_DIR}/small.cram" of="${CRAM_INVALID_DIR}/truncated.cram" bs=1000 count=1
    echo "Created truncated CRAM file"
fi

echo "Test data preparation complete." 