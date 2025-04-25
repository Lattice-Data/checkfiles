# Docker Guide for Checkfiles

This directory contains Docker configuration for running the Checkfiles validation tool in a containerized environment.

## Quick Start

```bash
# Build and run from project root
docker-compose -f docker/docker-compose.yml up

# Or cd into docker directory
cd docker
docker-compose up
```

## Features

- Single container with all dependencies pre-installed
- Rust components pre-compiled
- Python environment configured
- No need to install Rust, Python, or AWS tools locally

## Usage Examples

### Run validation on a single file
```bash
docker-compose -f docker/docker-compose.yml run checkfiles python -m src.main --file test_data/sample.fastq
```

### Run with custom AWS credentials
```bash
export AWS_ACCESS_KEY_ID=your-key-id
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-west-2
docker-compose -f docker/docker-compose.yml up
```

### Run interactively for debugging
```bash
docker-compose -f docker/docker-compose.yml run --entrypoint bash checkfiles
```

## Development

The Docker setup mounts your local `src` directory, allowing you to make code changes without rebuilding the image.

To apply changes to Rust components or dependencies:
```bash
docker-compose -f docker/docker-compose.yml build --no-cache
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| AWS_ACCESS_KEY_ID | AWS access key | None |
| AWS_SECRET_ACCESS_KEY | AWS secret key | None |
| AWS_DEFAULT_REGION | AWS region | None |

## Stopping Docker Containers

### Stop containers but preserve data
```bash
# If running in foreground with docker-compose up
# Press CTRL+C

# If running in background or from another terminal
docker-compose -f docker/docker-compose.yml down
```

### Clean up everything
```bash
# Stop containers and remove volumes/networks
docker-compose -f docker/docker-compose.yml down -v

# To also remove the built images
docker-compose -f docker/docker-compose.yml down -v --rmi all
```

### View running containers
```bash
docker ps
```

### Stop a specific container
```bash
docker stop <container_id>
```
```

## Troubleshooting

### Permission issues
If you encounter permission problems:
```bash
sudo chown -R $(id -u):$(id -g) .
```

### Library not found
If the Rust library can't be found:
- Verify the container has the correct paths by running:
```bash
docker-compose -f docker/docker-compose.yml run checkfiles sh -c 'ls -la /opt/checkfiles/lib'
```

## Production Use

For production, consider using the pre-built image from our registry:
```bash
docker pull example.com/checkfiles:latest
```