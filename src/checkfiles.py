import time
import argparse
import gzip
import os

EPILOG = '''
Run sanity checks on files.

Examples:

    python %(prog)s --mode production --accessions accessions.txt
    python %(prog)s --mode production --accesssions LATDF101HHH,LATDF102HHH,LATDF100HHH
    python %(prog)s --mode production --query "report/?type=RawSequenceFile&derived_from=/sequencing-runs/2a12eb7b-ed78-466a-9552-7512bdd7f45f/"
    python %(prog)s --s3-file s3://submissions-czi012eye/chen_2020/19D014_NeuNT_2_outs/raw_feature_bc_matrix.h5 --file-format hdf5

This relies on local variables to be defined based on the --mode you provide
to direct the updates to a server and to provide permissions
For example, if specifying --mode production, to make the changes on a local instance,
the following variables need to be defined...
PRODUCTION_KEY, PRODUCTION_SECRET, PRODUCTION_SERVER

For more details:

        python %(prog)s --help
'''

def generate_report():
    # First create the regular TSV file
    with open('/home/ubuntu/checkfiles/report.tsv', 'w') as f:
        for i in range(1, 3):
            f.write(f"{i}\n")
            f.flush() 
            print(f"Added number {i} to report, waiting 2 minutes...")
            time.sleep(5) 
    
    # Now gzip it
    with open('/home/ubuntu/checkfiles/report.tsv', 'rb') as f_in:
        with gzip.open('/home/ubuntu/checkfiles/report.tsv.gz', 'wb') as f_out:
            f_out.write(f_in.read())
    
    # Remove the original uncompressed file
    #os.remove('/home/ubuntu/checkfiles/report.tsv')

def main():
    args = getArgs()
    print("CHECKFILES STARTED")
    print("Generating report...")
    generate_report()
    time.sleep(60)  # Reduced sleep time for testing
    print("CHECKFILES FINISHED")



def getArgs():
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('--mode', '-m',
                        help='The machine to run on.')
    parser.add_argument('--update',
                        default=False,
                        action='store_true',
                        help='Let the script proceed with the changes.  Default is False'),
    parser.add_argument('--query', '-q',
                        help="override the file search query, e.g. 'accession=ENCFF000ABC'")
    parser.add_argument('--accessions', '-a',
                        help='one or more file accessions to check, comma separated or a file containing a list of file accessions to check')
    parser.add_argument('--include-validated',
                        default=False,
                        action='store_true',
                        help='Check all files even if they are validated=True in the Lattice database')
    parser.add_argument('--s3-file',
                        help="path to a file at s3 to check, comma separated or a file containing a list of file accessions to check")
    parser.add_argument('--ext-file',
                        help="path to a file elsewhere to check")
    parser.add_argument('--file-format',
                        help='the specified file format if an s3-file or local-file is being checked')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    
    main()