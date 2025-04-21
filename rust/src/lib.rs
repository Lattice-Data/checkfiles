use std::fs::File;
use std::io::{BufRead, BufReader};
use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use pyo3::types::{PyBytes, PyDict};
use std::collections::HashMap;

/// Validate a FASTQ input stream for correct format
/// 
/// This function can process any type that implements BufRead
fn validate_fastq_stream<R: BufRead>(reader: R) -> Result<bool, String> {
    let mut line_count = 0;
    let mut lines = reader.lines();
    
    while let Some(header_result) = lines.next() {
        // Process header line (should start with @)
        let header = match header_result {
            Ok(line) => line,
            Err(e) => return Err(format!("Error reading line {}: {}", line_count + 1, e)),
        };
        
        if !header.starts_with('@') {
            return Ok(false);
        }
        
        // Process sequence line
        let sequence = match lines.next() {
            Some(Ok(line)) => line,
            Some(Err(e)) => return Err(format!("Error reading sequence line: {}", e)),
            None => return Ok(false), // Unexpected EOF
        };
        
        // Store sequence length for comparison
        let sequence_length = sequence.trim().len();
        
        // Process quality header line (should start with +)
        let quality_header = match lines.next() {
            Some(Ok(line)) => line,
            Some(Err(e)) => return Err(format!("Error reading quality header: {}", e)),
            None => return Ok(false), // Unexpected EOF
        };
        
        if !quality_header.starts_with('+') {
            return Ok(false);
        }
        
        // Process quality line
        let quality = match lines.next() {
            Some(Ok(line)) => line,
            Some(Err(e)) => return Err(format!("Error reading quality line: {}", e)),
            None => return Ok(false), // Unexpected EOF
        };
        
        // Check sequence and quality lengths match
        let quality_length = quality.trim().len();
        if sequence_length != quality_length {
            return Ok(false);
        }
        
        line_count += 4;
    }
    
    // A valid FASTQ file should have a multiple of 4 lines
    Ok(line_count % 4 == 0 && line_count > 0)
}

/// Python-facing function to validate a FASTQ file
#[pyfunction]
fn validate_fastq(filename: &str) -> PyResult<bool> {
    let file = match File::open(filename) {
        Ok(file) => file,
        Err(e) => return Err(PyValueError::new_err(format!("Cannot open file {}: {}", filename, e))),
    };
    
    let reader = BufReader::new(file);
    match validate_fastq_stream(reader) {
        Ok(result) => Ok(result),
        Err(e) => Err(PyValueError::new_err(e)),
    }
}

/// Python-facing function to validate a FASTQ stream from bytes
#[pyfunction]
fn validate_fastq_from_bytes(_py: Python, data: &PyBytes) -> PyResult<bool> {
    let bytes = data.as_bytes();
    let cursor = std::io::Cursor::new(bytes);
    let reader = BufReader::new(cursor);
    
    match validate_fastq_stream(reader) {
        Ok(result) => Ok(result),
        Err(e) => Err(PyValueError::new_err(e)),
    }
}

/// Calculate statistics for a FASTQ stream
fn fastq_stats_stream<R: BufRead>(reader: R) -> Result<HashMap<String, usize>, String> {
    let mut read_count = 0;
    let mut total_length = 0;
    let mut min_length = usize::MAX;
    let mut max_length = 0;
    let mut lines = reader.lines();
    
    while let Some(header_result) = lines.next() {
        // Skip header line
        if header_result.is_err() {
            return Err("Error reading header line".to_string());
        }
        
        // Process sequence line
        let sequence = match lines.next() {
            Some(Ok(line)) => line,
            _ => return Err("Error reading sequence line".to_string()),
        };
        
        // Update statistics
        let length = sequence.trim().len();
        read_count += 1;
        total_length += length;
        min_length = min_length.min(length);
        max_length = max_length.max(length);
        
        // Skip quality header and quality line
        if lines.next().is_none() || lines.next().is_none() {
            return Err("Incomplete FASTQ record".to_string());
        }
    }
    
    let mut stats = HashMap::new();
    
    if read_count > 0 {
        stats.insert("read_count".to_string(), read_count);
        stats.insert("min_length".to_string(), min_length);
        stats.insert("max_length".to_string(), max_length);
        stats.insert("total_length".to_string(), total_length);
    } else {
        stats.insert("read_count".to_string(), 0);
        stats.insert("min_length".to_string(), 0);
        stats.insert("max_length".to_string(), 0);
        stats.insert("total_length".to_string(), 0);
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