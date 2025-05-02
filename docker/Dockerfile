# Checkfiles Validation Service Dockerfile
# 
# This Dockerfile builds a container for the Checkfiles validation service.
# It includes all required dependencies for processing and validating
# various file formats including FASTQ, BAM, and CRAM files.
#
# Maintainer: [Your Organization/Team]
# Last updated: $(date +'%Y-%m-%d')

FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONPATH="${PYTHONPATH}:/app" \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    SAMTOOLS_VERSION=1.17

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    python3-pip \
    gcc \
    g++ \
    libhdf5-dev \
    python3-dev \
    # Dependencies for samtools
    build-essential \
    wget \
    bzip2 \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    libssl-dev \
    libncurses5-dev \
    libncursesw5-dev \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI with specific versions to ensure compatibility
RUN pip3 install --no-cache-dir \
    botocore==1.31.17 \
    awscli==1.29.17 \
    boto3==1.28.17


# Install samtools for BAM/CRAM validation
RUN wget https://github.com/samtools/samtools/releases/download/${SAMTOOLS_VERSION}/samtools-${SAMTOOLS_VERSION}.tar.bz2 && \
    tar -xjf samtools-${SAMTOOLS_VERSION}.tar.bz2 && \
    cd samtools-${SAMTOOLS_VERSION} && \
    ./configure --prefix=/usr/local && \
    make && \
    make install && \
    cd .. && \
    rm -rf samtools-${SAMTOOLS_VERSION} samtools-${SAMTOOLS_VERSION}.tar.bz2

# Create required directories
RUN mkdir -p /opt/checkfiles /app/logs

# Copy Python code and requirements
COPY src/requirements.txt /app/
COPY src /app/src
COPY setup.py pyproject.toml /app/

# Create path wrapper script
RUN echo '#!/bin/bash\n\
python /app/src/checkfiles.py "$@"\n\
' > /app/run.sh && chmod +x /app/run.sh

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e .

# Make the script executable
RUN chmod +x /app/src/checkfiles.py

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0 if __import__('importlib').util.find_spec('src') else 1)"

# Command to run when container starts
ENTRYPOINT ["/app/run.sh"]
CMD ["--help"]
