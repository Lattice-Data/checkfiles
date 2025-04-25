# Stage 1: Build Rust components
FROM rust:1.72 as rust-builder

WORKDIR /build
COPY rust /build

# Build the Rust library
RUN cargo build --release

# Stage 2: Python environment
FROM python:3.8-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Create required directories
RUN mkdir -p /opt/checkfiles/lib /opt/checkfiles/python/fastq_validator

# Copy Python code
COPY src /app/src
COPY setup.py pyproject.toml /app/

# Copy built Rust library from previous stage
COPY --from=rust-builder /build/target/release/libfastq_validator.so /opt/checkfiles/lib/

# Create Python package structure for Rust bindings
COPY packer/scripts/install_rust_dependencies.sh /tmp/
RUN grep -A35 "__init__.py" /tmp/install_rust_dependencies.sh | tail -n +2 | sed '/^EOF/q' | sed '$d' > /opt/checkfiles/python/fastq_validator/__init__.py

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Set up environment variables
ENV PYTHONPATH="${PYTHONPATH}:/app:/opt/checkfiles/python"
ENV LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:/opt/checkfiles/lib"

# Command to run when container starts
ENTRYPOINT ["python", "-m", "src.main"]
