//! Error types for officeplane-core

use pyo3::exceptions::PyRuntimeError;
use pyo3::PyErr;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum OfficePlaneError {
    #[error("LibreOffice connection failed: {0}")]
    ConnectionFailed(String),

    #[error("Conversion failed: {0}")]
    ConversionFailed(String),

    #[error("Render failed: {0}")]
    RenderFailed(String),

    #[error("Pool exhausted: no available instances")]
    PoolExhausted,

    #[error("Timeout: operation took too long")]
    Timeout,

    #[error("Invalid input: {0}")]
    InvalidInput(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("MuPDF error: {0}")]
    MuPdf(String),
}

impl From<OfficePlaneError> for PyErr {
    fn from(err: OfficePlaneError) -> PyErr {
        PyRuntimeError::new_err(err.to_string())
    }
}

pub type Result<T> = std::result::Result<T, OfficePlaneError>;
