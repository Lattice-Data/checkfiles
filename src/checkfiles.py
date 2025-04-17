import time
import argparse
import gzip
import os

def generate_report():
    # First create the regular TSV file
    with open('/home/ubuntu/checkfiles/report.tsv', 'w') as f:
        for i in range(1, 5):
            f.write(f"{i}\n")
            f.flush() 
            print(f"Added number {i} to report, waiting 2 minutes...")
            time.sleep(30) 
    
    # Now gzip it
    with open('/home/ubuntu/checkfiles/report.tsv', 'rb') as f_in:
        with gzip.open('/home/ubuntu/checkfiles/report.tsv.gz', 'wb') as f_out:
            f_out.write(f_in.read())
    
    # Remove the original uncompressed file
    os.remove('/home/ubuntu/checkfiles/report.tsv')

def main(args):
    print("CHECKFILES STARTED")
    print("Generating report...")
    generate_report()
    time.sleep(10)  # Reduced sleep time for testing
    print("CHECKFILES FINISHED")

# Start script
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Checkfiles argumentparser')
    parser.add_argument('--uuid', type=str,
                        help='UUID of the fileobject to be checked.')
    parser.add_argument(
        '--server', type=str, help='igvf instance to check. https://api.sandbox.igvf.org for example')
    parser.add_argument('--portal-key-id', type=str, help='Portal key id')
    parser.add_argument('--portal-secret-key', type=str,
                        help='Portal secret key')
    parser.add_argument('--patch', action='store_true',
                        help='Patch the checked objects.')
    parser.add_argument('--number-of-files', type=str,
                        help='Use this option to limit the number of pending files to check. If unset, all the pending files will be checked.')
    parser.add_argument('--ignore-active-credentials', action='store_true',
                        help='If this flag is set, then we omit checking if the file has unexpired upload credentials. There be dragons here, someone might change the underlying file after checking.')

    args = parser.parse_args()
    main(args)