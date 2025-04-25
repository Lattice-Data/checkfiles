FROM python:3.8-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Create required directories
RUN mkdir -p /opt/checkfiles

# Copy Python code
COPY src /app/src
COPY setup.py pyproject.toml /app/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Set up environment variables
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Command to run when container starts
ENTRYPOINT ["python", "-m", "src.main"]
