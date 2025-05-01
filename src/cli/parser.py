"""Argument parsing for checkfiles command-line interface."""

import argparse
import multiprocessing
from typing import Any

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for checkfiles utility.
    
    Returns:
        Parsed command-line arguments
    """
    # Get the number of available CPUs for default thread count
    default_threads = multiprocessing.cpu_count()
    
    parser = argparse.ArgumentParser(
        description='Checkfiles utility - validates file formats like FASTQ. Accepts files from local paths, S3, or backend API query.',
        epilog='''Examples:
  # Validate a single local file
  ./src/checkfiles.py -f fastq -l path/to/file.fastq.gz
  
  # Validate multiple local files
  ./src/checkfiles.py -f fastq -l path/to/file1.fastq.gz,path/to/file2.fastq.gz
  
  # Validate multiple S3 files
  ./src/checkfiles.py -f fastq -s3 s3://bucket/file1.fastq.gz,s3://bucket/file2.fastq.gz
  
  # Validate files using a backend query
  ./src/checkfiles.py --backend-uri https://example.com/api/ --query type=File&accession=ABCD1234
  
  Note: Only one file source (-l, -s3, or --backend-uri/--query) can be used at a time.
  Note: When using -l or -s3, the -f parameter is required. When using --backend-uri and --query, -f must not be provided.
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-s3', '--s3-file', help='Specify S3 file(s) as comma-separated paths')
    parser.add_argument('-l', '--local-file', help='Specify local file(s) to validate as comma-separated paths')
    parser.add_argument('-f', '--file-format', 
                        help='Specify the file format (e.g., fastq). Required when using -l or -s3, but must not be used with --backend-uri and --query.')
    parser.add_argument('-d', '--debug', action='store_true', 
                        help='Enable debug output')
    parser.add_argument('-t', '--threads', type=int, default=default_threads, 
                        help=f'Number of threads for parallel processing (default: {default_threads}, based on CPU count)')
    parser.add_argument('-q', '--quiet', action='store_true', 
                        help='Suppress progress indicators and only show final results')
    parser.add_argument('--log-file', 
                        help='Path to log file (default: ./logs/checkfiles_debug.log)')
    parser.add_argument('--backend-uri',
                        help='Backend URI for API calls')
    parser.add_argument('--query',
                        help='Query string for filtering files')
    
    return parser.parse_args() 