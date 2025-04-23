#!/usr/bin/env python3

import argparse
import sys

def parse_arguments():
    parser = argparse.ArgumentParser(description='Checkfiles utility')
    
    parser.add_argument('-m', '--mode', help='Specify the mode')
    parser.add_argument('-q', '--query', help='Specify the query')
    parser.add_argument('-s3', '--s3-file', help='Specify the S3 file')
    parser.add_argument('-l', '--local-file', help='Specify a local file to validate')
    parser.add_argument('-u', '--update', action='store_true', help='Update flag')
    parser.add_argument('-f', '--file-format', help='Specify the file format')
    
    return parser.parse_args()

def main():
    args = parse_arguments()

    
    # Check if file format is fastq
    if args.file_format and args.file_format.lower() == "fastq":
        try:
            from src.validators.fastq import FastqValidator
            validator = FastqValidator()
            
            # Check if local file is provided
            if args.local_file:
                print(f"Running FastqValidator on local file: {args.local_file}")
                results = validator.validate_file(args.local_file)
                print(f"Validation results: {results}")
            # Check if S3 file is provided
            elif args.s3_file:
                print(f"Running FastqValidator on S3 file: {args.s3_file}")
                # Here you would implement S3 file handling
                print("S3 validation not implemented yet")
            elif args.mode == "stream":
                print("Running FastqValidator in stream mode")
                # Example of stream validation
                results = validator.validate_stream(sys.stdin.buffer)
                print(f"Validation results: {results}")
            else:
                print("Please provide a local file, S3 file, or stream mode for FASTQ validation")
                
        except ImportError as e:
            print(f"Error importing FastqValidator: {e}")
            print("Make sure the Rust implementation is properly installed")

if __name__ == "__main__":
    main()
