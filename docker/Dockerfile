FROM python:3.8-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    python3-pip \
    # Dependencies for samtools
    build-essential \
    wget \
    bzip2 \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI with specific versions to ensure compatibility
RUN pip3 install --no-cache-dir \
    botocore==1.31.17 \
    awscli==1.29.17 \
    boto3==1.28.17

# Install samtools for BAM/CRAM validation
RUN wget https://github.com/samtools/samtools/releases/download/1.17/samtools-1.17.tar.bz2 && \
    tar -xjf samtools-1.17.tar.bz2 && \
    cd samtools-1.17 && \
    ./configure --prefix=/usr/local && \
    make && \
    make install && \
    cd .. && \
    rm -rf samtools-1.17 samtools-1.17.tar.bz2

# Create required directories
RUN mkdir -p /opt/checkfiles

# Copy Python code and requirements
COPY src/requirements.txt /app/
COPY src /app/src
COPY setup.py pyproject.toml /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -e .

# Set up environment variables
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Make the script executable
RUN chmod +x /app/src/checkfiles.py

# Command to run when container starts
ENTRYPOINT ["python", "/app/src/checkfiles.py"]
CMD ["--help"]
