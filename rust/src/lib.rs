use std::fs::File;
use std::io::{BufRead, BufReader};
use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use pyo3::types::{PyBytes, PyDict};
use std::collections::HashMap;
use regex::Regex;
use std::sync::Mutex;

// Thread-safe storage for the last parsed collections
lazy_static::lazy_static! {
    static ref LAST_MACHINE_IDS: Mutex<String> = Mutex::new(String::new());
    static ref LAST_FLOWCELLS: Mutex<String> = Mutex::new(String::new());
    static ref LAST_LANES: Mutex<String> = Mutex::new(String::new());
    static ref LAST_INSTRUMENT_TYPES: Mutex<String> = Mutex::new(String::new());
}

// FASTQ format regex patterns
lazy_static::lazy_static! {
    static ref SEQ_REGEX: Regex = Regex::new(r"^[A-Za-z.~]+$").unwrap();
    static ref QUAL_REGEX: Regex = Regex::new(r"^[!-~]+$").unwrap();
    
    // Patterns for FASTQ readname parsing
    static ref TYPE1_PATTERN: Regex = Regex::new(r"^@([a-zA-Z\d]+[a-zA-Z\d_-]*):([a-zA-Z\d-]+):([a-zA-Z\d_-]+):(\d+):\d+:\d+:\d+").unwrap();
    static ref TYPE2_PATTERN: Regex = Regex::new(r"^@([a-zA-Z\d]+[a-zA-Z\d_-]*):(\d+):\d+:\d+:\d+").unwrap();
    
    // Instrument ID patterns
    static ref NOVASEQ_X_PLUS: Regex = Regex::new(r"^LH[0-9]{5}$").unwrap();
    static ref NOVASEQ_6000: Regex = Regex::new(r"^A[0-9]{5}$").unwrap();
    static ref NOVASEQ_6000_R: Regex = Regex::new(r"^A[0-9]{5}R$").unwrap();
    static ref HISEQ_X: Regex = Regex::new(r"^E[0-9]{5}$").unwrap();
    static ref HISEQ_4000: Regex = Regex::new(r"^K[0-9]{5}$").unwrap();
    static ref HISEQ_4000_R: Regex = Regex::new(r"^K[0-9]{5}R$").unwrap();
    static ref HISEQ_3000: Regex = Regex::new(r"^J[0-9]{5}$").unwrap();
    static ref HISEQ_2500: Regex = Regex::new(r"^D[0-9]{5}$").unwrap();
    static ref HISEQ_2500_HWI: Regex = Regex::new(r"^HWI-D[0-9]{5}$").unwrap();
    static ref HISEQ_1500: Regex = Regex::new(r"^C[0-9]{5}$").unwrap();
    static ref HISEQ_1500_HWI: Regex = Regex::new(r"^HWI-C[0-9]{5}$").unwrap();
    static ref NEXTSEQ_2000: Regex = Regex::new(r"^VH[0-9]{5}$").unwrap();
    static ref NEXTSEQ_550: Regex = Regex::new(r"^(NB|NS)55[0-9]{4}$").unwrap();
    static ref NEXTSEQ_500: Regex = Regex::new(r"^(NB|NS)50[0-9]{4}$").unwrap();
}

/// Helper function to identify instrument type from machine ID
fn get_instrument_type(machine_id: &str) -> Option<String> {
    if NOVASEQ_X_PLUS.is_match(machine_id) {
        Some("Illumina NovaSeq X Plus (EFO:0022841)".to_string())
    } else if NOVASEQ_6000.is_match(machine_id) || NOVASEQ_6000_R.is_match(machine_id) {
        Some("Illumina NovaSeq 6000 (EFO:0008637)".to_string())
    } else if HISEQ_X.is_match(machine_id) {
        Some("Illumina HiSeq X (EFO:0008567)".to_string())
    } else if HISEQ_4000.is_match(machine_id) || HISEQ_4000_R.is_match(machine_id) {
        Some("Illumina HiSeq 4000 (EFO:0008563)".to_string())
    } else if HISEQ_3000.is_match(machine_id) {
        Some("Illumina HiSeq 3000 (EFO:0008564)".to_string())
    } else if HISEQ_2500.is_match(machine_id) || HISEQ_2500_HWI.is_match(machine_id) {
        Some("Illumina HiSeq 2500 (EFO:0008565)".to_string())
    } else if HISEQ_1500.is_match(machine_id) || HISEQ_1500_HWI.is_match(machine_id) {
        Some("Illumina HiSeq 1500 (EFO:0011027)".to_string())
    } else if NEXTSEQ_2000.is_match(machine_id) {
        Some("Illumina NextSeq 2000 (EFO:0010963)".to_string())
    } else if NEXTSEQ_550.is_match(machine_id) {
        Some("Illumina NextSeq 550 (EFO:0008566)".to_string())
    } else if NEXTSEQ_500.is_match(machine_id) {
        Some("Illumina NextSeq 500 (EFO:0009173)".to_string())
    } else {
        None
    }
}

/// Result of FASTQ validation with detailed error information
struct FastqValidationResult {
    valid: bool,
    error_message: Option<String>,
    line_number: Option<usize>,
}

impl FastqValidationResult {
    fn new_valid() -> Self {
        FastqValidationResult {
            valid: true,
            error_message: None,
            line_number: None,
        }
    }

    fn new_invalid(error_message: String, line_number: usize) -> Self {
        FastqValidationResult {
            valid: false,
            error_message: Some(error_message),
            line_number: Some(line_number),
        }
    }
}

/// Validate a FASTQ input stream for correct format
/// 
/// This function checks:
/// 1. Every block starts with @ (header)
/// 2. Header line matches the required seqname pattern
/// 3. Sequence line contains only valid sequence characters
/// 4. + line follows the sequence, with optional matching seqname
/// 5. Quality line contains valid quality characters
/// 6. Sequence and quality lines have equal length
fn validate_fastq_stream<R: BufRead>(reader: R) -> FastqValidationResult {
    let mut line_count: usize = 0;
    let mut lines = reader.lines().peekable();
    
    // Process the file block by block
    while let Some(Ok(header_line)) = lines.next() {
        line_count += 1;
        
        // Check header line starts with @
        if !header_line.starts_with('@') {
            return FastqValidationResult::new_invalid(
                format!("Header line must start with @: '{}'", header_line),
                line_count
            );
        }
        
        // Get sequence line
        let seq_line = match lines.next() {
            Some(Ok(line)) => line,
            _ => return FastqValidationResult::new_invalid(
                "Unexpected end of file after header line".to_string(),
                line_count + 1
            ),
        };
        line_count += 1;
        
        // Validate sequence characters
        if !SEQ_REGEX.is_match(&seq_line) {
            return FastqValidationResult::new_invalid(
                format!("Invalid sequence characters: '{}'", seq_line),
                line_count
            );
        }
        
        // Get + line
        let plus_line = match lines.next() {
            Some(Ok(line)) => line,
            _ => return FastqValidationResult::new_invalid(
                "Unexpected end of file after sequence line".to_string(),
                line_count + 1
            ),
        };
        line_count += 1;
        
        // Check + line format
        if !plus_line.starts_with('+') {
            return FastqValidationResult::new_invalid(
                format!("Quality header must start with +: '{}'", plus_line),
                line_count
            );
        }
        
        // If + is followed by a seqname, check it matches the header seqname exactly
        if plus_line.len() > 1 {
            let plus_seqname = &plus_line[1..];  // Everything after +
            let header_seqname = &header_line[1..];  // Everything after @
            if plus_seqname != header_seqname {
                return FastqValidationResult::new_invalid(
                    format!("Seqname in + line ('{}') doesn't match header seqname ('{}')", 
                           plus_seqname, header_seqname),
                    line_count
                );
            }
        }
        
        // Get quality line
        let qual_line = match lines.next() {
            Some(Ok(line)) => line,
            _ => return FastqValidationResult::new_invalid(
                "Unexpected end of file after + line".to_string(),
                line_count + 1
            ),
        };
        line_count += 1;
        
        // Validate quality characters
        if !QUAL_REGEX.is_match(&qual_line) {
            return FastqValidationResult::new_invalid(
                format!("Invalid quality characters: '{}'", qual_line),
                line_count
            );
        }
        
        // Check sequence and quality line lengths match
        if seq_line.len() != qual_line.len() {
            return FastqValidationResult::new_invalid(
                format!("Sequence length ({}) and quality length ({}) don't match", 
                       seq_line.len(), qual_line.len()),
                line_count
            );
        }
        
        // Check for valid quality values (ASCII 33-126)
        for (i, c) in qual_line.chars().enumerate() {
            let ascii_val = c as u32;
            if ascii_val < 33 || ascii_val > 126 {
                return FastqValidationResult::new_invalid(
                    format!("Invalid quality value at position {}: ASCII {}", i + 1, ascii_val),
                    line_count
                );
            }
        }
    }
    
    // A valid FASTQ file should have at least one block
    if line_count == 0 {
        return FastqValidationResult::new_invalid(
            "Empty FASTQ file".to_string(), 
            0
        );
    }
    
    // Check if file has a complete number of blocks
    if line_count % 4 != 0 {
        return FastqValidationResult::new_invalid(
            format!("Incomplete FASTQ block. Line count ({}) is not a multiple of 4", line_count),
            line_count
        );
    }
    
    FastqValidationResult::new_valid()
}

/// Python-facing function to validate a FASTQ file
#[pyfunction]
fn validate_fastq(py: Python, filename: &str) -> PyResult<PyObject> {
    let file = match File::open(filename) {
        Ok(file) => file,
        Err(e) => return Err(PyValueError::new_err(format!("Cannot open file {}: {}", filename, e))),
    };
    
    let reader = BufReader::new(file);
    let result = validate_fastq_stream(reader);
    
    // Convert usize to u64 for Python compatibility
    let line_number = result.line_number.map(|n| n as u64);
    
    // Create Python tuple directly without using eval
    let tuple = (
        result.valid,
        result.error_message,
        line_number
    ).into_py(py);
    
    Ok(tuple)
}

/// Python-facing function to validate a FASTQ stream from bytes
#[pyfunction]
fn validate_fastq_from_bytes(py: Python, data: &PyBytes) -> PyResult<PyObject> {
    let bytes = data.as_bytes();
    let cursor = std::io::Cursor::new(bytes);
    let reader = BufReader::new(cursor);
    
    let result = validate_fastq_stream(reader);
    
    // Convert usize to u64 for Python compatibility
    let line_number = result.line_number.map(|n| n as u64);
    
    // Create Python tuple directly without using eval
    let tuple = (
        result.valid,
        result.error_message,
        line_number
    ).into_py(py);
    
    Ok(tuple)
}

/// Calculate statistics for a FASTQ stream
fn fastq_stats_stream<R: BufRead>(reader: R) -> Result<HashMap<String, usize>, String> {
    let mut read_count = 0;
    let mut total_length = 0;
    let mut min_length = usize::MAX;
    let mut max_length = 0;
    let mut base_counts = HashMap::new();
    let mut quality_sum = 0;
    let mut lines = reader.lines();
    
    // Add collections for readname information (keep this)
    let mut machine_ids = std::collections::HashSet::new();
    let mut flowcells = std::collections::HashSet::new();
    let mut lanes = std::collections::HashSet::new();
    let mut instrument_types = std::collections::HashSet::new();
    
    while let Some(header_result) = lines.next() {
        // Process header line
        let header = match header_result {
            Ok(line) => line,
            Err(e) => return Err(format!("Error reading header line: {}", e)),
        };
        
        // Parse readname for Type 1 (full Illumina)
        if let Some(caps) = TYPE1_PATTERN.captures(&header) {
            let machine_id = caps.get(1).unwrap().as_str().to_string();
            let flowcell_id = caps.get(3).unwrap().as_str().to_string();
            let lane_str = caps.get(4).unwrap().as_str();
            
            if let Ok(lane) = lane_str.parse::<usize>() {
                lanes.insert(lane);
            }
            
            machine_ids.insert(machine_id.clone());
            flowcells.insert(flowcell_id);
            
            // Check for instrument type match
            if let Some(instrument) = get_instrument_type(&machine_id) {
                instrument_types.insert(instrument);
            }
        } 
        // Parse readname for Type 2 (partial Illumina)
        else if let Some(caps) = TYPE2_PATTERN.captures(&header) {
            let machine_id = caps.get(1).unwrap().as_str().to_string();
            let lane_str = caps.get(2).unwrap().as_str();
            
            if let Ok(lane) = lane_str.parse::<usize>() {
                lanes.insert(lane);
            }
            
            machine_ids.insert(machine_id.clone());
            
            // Check for instrument type match
            if let Some(instrument) = get_instrument_type(&machine_id) {
                instrument_types.insert(instrument);
            }
        }
        // Type 3 readnames (no special parsing needed)
        
        // Process sequence line
        let sequence = match lines.next() {
            Some(Ok(line)) => line,
            _ => return Err("Error reading sequence line".to_string()),
        };
        
        // Count bases
        for base in sequence.chars() {
            *base_counts.entry(base).or_insert(0) += 1;
        }
        
        // Update statistics
        let length = sequence.len();
        read_count += 1;
        total_length += length;
        min_length = min_length.min(length);
        max_length = max_length.max(length);
        
        // Skip + line
        if lines.next().is_none() {
            return Err("Incomplete FASTQ record (missing + line)".to_string());
        }
        
        // Process quality line
        let quality = match lines.next() {
            Some(Ok(line)) => line,
            _ => return Err("Error reading quality line".to_string()),
        };
        
        // Calculate quality stats
        for q in quality.chars() {
            quality_sum += (q as u32 - 33) as usize;
        }
    }
    
    let mut stats = HashMap::new();
    
    if read_count > 0 {
        stats.insert("read_count".to_string(), read_count);
        stats.insert("min_length".to_string(), min_length);
        stats.insert("max_length".to_string(), max_length);
        stats.insert("total_length".to_string(), total_length);
        stats.insert("avg_quality".to_string(), quality_sum / total_length);
        
        // Add base counts
        for (base, count) in base_counts {
            let base_key = format!("base_{}", base);
            stats.insert(base_key, count);
        }
        
        // For collections, we'll encode them as strings with counts
        // Format: "COUNT|item1|item2|item3"
        
        // Machine IDs
        let machine_ids_vec: Vec<String> = machine_ids.into_iter().collect();
        stats.insert("machine_ids_count".to_string(), machine_ids_vec.len());
        
        // Create a string with all machine IDs separated by "|"
        if !machine_ids_vec.is_empty() {
            let machine_ids_str = machine_ids_vec.join("|");
            stats.insert("machine_ids_data".to_string(), machine_ids_str.len());
            if let Ok(mut last_ids) = LAST_MACHINE_IDS.lock() {
                *last_ids = machine_ids_str;
            }
        }
        
        // Flowcells
        let flowcells_vec: Vec<String> = flowcells.into_iter().collect();
        stats.insert("flowcells_count".to_string(), flowcells_vec.len());
        
        if !flowcells_vec.is_empty() {
            let flowcells_str = flowcells_vec.join("|");
            stats.insert("flowcells_data".to_string(), flowcells_str.len());
            if let Ok(mut last_flowcells) = LAST_FLOWCELLS.lock() {
                *last_flowcells = flowcells_str;
            }
        }
        
        // Lanes
        let lanes_vec: Vec<usize> = lanes.into_iter().collect();
        stats.insert("lanes_count".to_string(), lanes_vec.len());
        
        if !lanes_vec.is_empty() {
            // Convert usize values to strings
            let lanes_str_vec: Vec<String> = lanes_vec.iter().map(|&l| l.to_string()).collect();
            let lanes_str = lanes_str_vec.join("|");
            stats.insert("lanes_data".to_string(), lanes_str.len());
            if let Ok(mut last_lanes) = LAST_LANES.lock() {
                *last_lanes = lanes_str;
            }
        }
        
        // Instrument types
        let instrument_types_vec: Vec<String> = instrument_types.into_iter().collect();
        stats.insert("instrument_types_count".to_string(), instrument_types_vec.len());
        
        if !instrument_types_vec.is_empty() {
            let instrument_types_str = instrument_types_vec.join("|");
            stats.insert("instrument_types_data".to_string(), instrument_types_str.len());
            if let Ok(mut last_types) = LAST_INSTRUMENT_TYPES.lock() {
                *last_types = instrument_types_str;
            }
        }
    } else {
        stats.insert("read_count".to_string(), 0);
        stats.insert("min_length".to_string(), 0);
        stats.insert("max_length".to_string(), 0);
        stats.insert("total_length".to_string(), 0);
        stats.insert("avg_quality".to_string(), 0);
        
        // Add empty collections data
        stats.insert("machine_ids_count".to_string(), 0);
        stats.insert("flowcells_count".to_string(), 0);
        stats.insert("lanes_count".to_string(), 0);
        stats.insert("instrument_types_count".to_string(), 0);
    }
    
    Ok(stats)
}

/// Python-facing function to get statistics from a FASTQ file
#[pyfunction]
fn fastq_stats(py: Python, filename: &str) -> PyResult<PyObject> {
    let file = match File::open(filename) {
        Ok(file) => file,
        Err(e) => return Err(PyValueError::new_err(format!("Cannot open file {}: {}", filename, e))),
    };
    
    let reader = BufReader::new(file);
    match fastq_stats_stream(reader) {
        Ok(stats) => {
            let dict = PyDict::new(py);
            
            // Make a clone of stats for iteration
            let stats_clone = stats.clone();
            
            // Iterate over the clone
            for (key, value) in stats_clone {
                dict.set_item(key, value)?;
            }
            
            // Calculate average if we have reads
            if let Some(read_count) = stats.get("read_count") {
                if let Some(total_length) = stats.get("total_length") {
                    if *read_count > 0 {
                        let avg_length = *total_length as f64 / *read_count as f64;
                        dict.set_item("avg_length", avg_length)?;
                    } else {
                        dict.set_item("avg_length", 0.0)?;
                    }
                }
            }
            
            Ok(dict.to_object(py))
        },
        Err(e) => Err(PyValueError::new_err(e)),
    }
}

/// Python-facing function to get statistics from a FASTQ byte stream
#[pyfunction]
fn fastq_stats_from_bytes(py: Python, data: &PyBytes) -> PyResult<PyObject> {
    let bytes = data.as_bytes();
    let cursor = std::io::Cursor::new(bytes);
    let reader = BufReader::new(cursor);
    
    match fastq_stats_stream(reader) {
        Ok(stats) => {
            let dict = PyDict::new(py);
            
            // Make a clone of stats for iteration
            let stats_clone = stats.clone();
            
            // Iterate over the clone
            for (key, value) in stats_clone {
                dict.set_item(key, value)?;
            }
            
            // Calculate average if we have reads
            if let Some(read_count) = stats.get("read_count") {
                if let Some(total_length) = stats.get("total_length") {
                    if *read_count > 0 {
                        let avg_length = *total_length as f64 / *read_count as f64;
                        dict.set_item("avg_length", avg_length)?;
                    } else {
                        dict.set_item("avg_length", 0.0)?;
                    }
                }
            }
            
            Ok(dict.to_object(py))
        },
        Err(e) => Err(PyValueError::new_err(e)),
    }
}

// Add functions to retrieve these values
#[pyfunction]
fn get_last_machine_ids() -> String {
    if let Ok(last_ids) = LAST_MACHINE_IDS.lock() {
        last_ids.clone()
    } else {
        String::new()
    }
}

#[pyfunction]
fn get_last_flowcells() -> String {
    if let Ok(last_flowcells) = LAST_FLOWCELLS.lock() {
        last_flowcells.clone()
    } else {
        String::new()
    }
}

#[pyfunction]
fn get_last_lanes() -> String {
    if let Ok(last_lanes) = LAST_LANES.lock() {
        last_lanes.clone()
    } else {
        String::new()
    }
}

#[pyfunction]
fn get_last_instrument_types() -> String {
    if let Ok(last_types) = LAST_INSTRUMENT_TYPES.lock() {
        last_types.clone()
    } else {
        String::new()
    }
}

/// A Python module implemented in Rust
#[pymodule]
fn fastq_validator(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validate_fastq, m)?)?;
    m.add_function(wrap_pyfunction!(validate_fastq_from_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(fastq_stats, m)?)?;
    m.add_function(wrap_pyfunction!(fastq_stats_from_bytes, m)?)?;
    
    m.add_function(wrap_pyfunction!(get_last_machine_ids, m)?)?;
    m.add_function(wrap_pyfunction!(get_last_flowcells, m)?)?;
    m.add_function(wrap_pyfunction!(get_last_lanes, m)?)?;
    m.add_function(wrap_pyfunction!(get_last_instrument_types, m)?)?;
    
    Ok(())
}