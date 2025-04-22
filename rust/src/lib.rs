use std::fs::File;
use std::io::{BufRead, BufReader};
use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use pyo3::types::{PyBytes, PyDict};
use std::collections::HashMap;
use regex::Regex;

// FASTQ format regex patterns
lazy_static::lazy_static! {
    static ref SEQNAME_REGEX: Regex = Regex::new(r"^[A-Za-z0-9_.:-]+").unwrap();
    static ref SEQ_REGEX: Regex = Regex::new(r"^[A-Za-z.~]+$").unwrap();
    static ref QUAL_REGEX: Regex = Regex::new(r"^[!-~]+$").unwrap();
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
        
        // Extract and validate seqname from header
        let seqname = &header_line[1..];
        if !SEQNAME_REGEX.is_match(seqname) {
            return FastqValidationResult::new_invalid(
                format!("Invalid sequence name format: '{}'", seqname),
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
        
        // If + is followed by a seqname, check it matches the header seqname
        if plus_line.len() > 1 {
            let plus_seqname = &plus_line[1..];
            if !plus_seqname.is_empty() && plus_seqname != seqname {
                return FastqValidationResult::new_invalid(
                    format!("Seqname in + line ('{}') doesn't match header seqname ('{}')", 
                           plus_seqname, seqname),
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
fn validate_fastq(filename: &str) -> PyResult<(bool, Option<String>, Option<usize>)> {
    let file = match File::open(filename) {
        Ok(file) => file,
        Err(e) => return Err(PyValueError::new_err(format!("Cannot open file {}: {}", filename, e))),
    };
    
    let reader = BufReader::new(file);
    let result = validate_fastq_stream(reader);
    
    Ok((result.valid, result.error_message, result.line_number))
}

/// Python-facing function to validate a FASTQ stream from bytes
#[pyfunction]
fn validate_fastq_from_bytes(_py: Python, data: &PyBytes) -> PyResult<(bool, Option<String>, Option<usize>)> {
    let bytes = data.as_bytes();
    let cursor = std::io::Cursor::new(bytes);
    let reader = BufReader::new(cursor);
    
    let result = validate_fastq_stream(reader);
    
    Ok((result.valid, result.error_message, result.line_number))
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
    
    while let Some(header_result) = lines.next() {
        // Process header line
        let _header = match header_result {
            Ok(line) => line,
            Err(e) => return Err(format!("Error reading header line: {}", e)),
        };
        
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
    } else {
        stats.insert("read_count".to_string(), 0);
        stats.insert("min_length".to_string(), 0);
        stats.insert("max_length".to_string(), 0);
        stats.insert("total_length".to_string(), 0);
        stats.insert("avg_quality".to_string(), 0);
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

/// A Python module implemented in Rust
#[pymodule]
fn fastq_validator(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(validate_fastq, m)?)?;
    m.add_function(wrap_pyfunction!(validate_fastq_from_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(fastq_stats, m)?)?;
    m.add_function(wrap_pyfunction!(fastq_stats_from_bytes, m)?)?;
    Ok(())
}