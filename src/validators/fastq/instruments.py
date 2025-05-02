"""
Module for identifying DNA sequencing instruments from machine IDs in FASTQ headers.
"""

import re
from typing import Optional

# Instrument ID patterns
NOVASEQ_X_PLUS = re.compile(r'^LH[0-9]{5}$')
NOVASEQ_6000 = re.compile(r'^A[0-9]{5}$')
NOVASEQ_6000_R = re.compile(r'^A[0-9]{5}R$')
HISEQ_X = re.compile(r'^E[0-9]{5}$')
HISEQ_4000 = re.compile(r'^K[0-9]{5}$')
HISEQ_4000_R = re.compile(r'^K[0-9]{5}R$')
HISEQ_3000 = re.compile(r'^J[0-9]{5}$')
HISEQ_2500 = re.compile(r'^D[0-9]{5}$')
HISEQ_2500_HWI = re.compile(r'^HWI-D[0-9]{5}$')
HISEQ_1500 = re.compile(r'^C[0-9]{5}$')
HISEQ_1500_HWI = re.compile(r'^HWI-C[0-9]{5}$')
NEXTSEQ_2000 = re.compile(r'^VH[0-9]{5}$')
NEXTSEQ_550 = re.compile(r'^(NB|NS)55[0-9]{4}$')
NEXTSEQ_500 = re.compile(r'^(NB|NS)50[0-9]{4}$')

def get_instrument_type(machine_id: str) -> Optional[str]:
    """
    Identify instrument type from machine ID in FASTQ header.
    
    Args:
        machine_id: Machine identifier string from FASTQ header
        
    Returns:
        Instrument type with EFO ontology ID, or None if not recognized
    """
    if NOVASEQ_X_PLUS.match(machine_id):
        return "Illumina NovaSeq X Plus (EFO:0022841)"
    elif NOVASEQ_6000.match(machine_id) or NOVASEQ_6000_R.match(machine_id):
        return "Illumina NovaSeq 6000 (EFO:0008637)"
    elif HISEQ_X.match(machine_id):
        return "Illumina HiSeq X (EFO:0008567)"
    elif HISEQ_4000.match(machine_id) or HISEQ_4000_R.match(machine_id):
        return "Illumina HiSeq 4000 (EFO:0008563)"
    elif HISEQ_3000.match(machine_id):
        return "Illumina HiSeq 3000 (EFO:0008564)"
    elif HISEQ_2500.match(machine_id) or HISEQ_2500_HWI.match(machine_id):
        return "Illumina HiSeq 2500 (EFO:0008565)"
    elif HISEQ_1500.match(machine_id) or HISEQ_1500_HWI.match(machine_id):
        return "Illumina HiSeq 1500 (EFO:0011027)"
    elif NEXTSEQ_2000.match(machine_id):
        return "Illumina NextSeq 2000 (EFO:0010963)"
    elif NEXTSEQ_550.match(machine_id):
        return "Illumina NextSeq 550 (EFO:0008566)"
    elif NEXTSEQ_500.match(machine_id):
        return "Illumina NextSeq 500 (EFO:0009173)"
    else:
        return None 