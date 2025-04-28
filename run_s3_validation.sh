#!/bin/bash
# run_s3_validation.sh - Run checkfiles Docker container with optimal settings for S3 validation

# Get the S3 path from command line argument
S3_FILE="$1"
FILE_FORMAT="${2:-fastq}"

if [ -z "$S3_FILE" ]; then
  echo "Usage: $0 <s3_path> [file_format]"
  echo "Example: $0 s3://mybucket/file.fastq.gz fastq"
  exit 1
fi

# Set AWS credentials from environment if available
if [ -z "$AWS_DEFAULT_REGION" ]; then
  export AWS_DEFAULT_REGION="us-west-1"
fi

echo "Running checkfiles validation with optimized settings..."
echo "S3 File: $S3_FILE"
echo "Format: $FILE_FORMAT"

# Use docker compose to run with proper memory and resource limits
docker compose -f docker/docker-compose.yml run \
  --memory=4g \
  --memory-reservation=2g \
  --memory-swap=4g \
  --cpus=2 \
  checkfiles \
  -f "$FILE_FORMAT" \
  -s3 "$S3_FILE" \
  -d

# Check exit status
if [ $? -eq 0 ]; then
  echo "Validation completed successfully."
else
  echo "Validation failed. Check logs for details."
  exit 1
fi 