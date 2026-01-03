//! OfficePlane Core - High-performance native middleware
//!
//! This crate provides high-performance document conversion and rendering
//! with Python bindings via PyO3.

pub mod error;
pub mod pool;
pub mod render;
pub mod uno;

use std::time::Instant;

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};
use sha2::Digest as Sha2Digest;
use tracing_subscriber::EnvFilter;

use crate::error::OfficePlaneError;
use crate::pool::{get_global_pool, init_global_pool};
use crate::render::{pdf_to_images, ImageFormat_};

/// Initialize the native driver with a LibreOffice pool
#[pyfunction]
#[pyo3(signature = (pool_size=6, start_port=2002, timeout_secs=45))]
fn init_pool(pool_size: usize, start_port: u16, timeout_secs: u64) -> PyResult<()> {
    // Initialize tracing
    let _ = tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .try_init();

    init_global_pool(pool_size, start_port, timeout_secs);
    Ok(())
}

/// Get pool status as a dictionary
#[pyfunction]
fn pool_status(py: Python<'_>) -> PyResult<PyObject> {
    let pool = get_global_pool()
        .ok_or_else(|| OfficePlaneError::ConnectionFailed("Pool not initialized".to_string()))?;

    let status = pool.status();
    let dict = PyDict::new_bound(py);
    dict.set_item("total", status.total)?;
    dict.set_item("ready", status.ready)?;

    let instances = PyList::empty_bound(py);
    for inst in status.instances {
        let inst_dict = PyDict::new_bound(py);
        inst_dict.set_item("port", inst.port)?;
        inst_dict.set_item("ready", inst.ready)?;
        inst_dict.set_item("restarts", inst.restarts)?;
        inst_dict.set_item("last_error", inst.last_error)?;
        instances.append(inst_dict)?;
    }
    dict.set_item("instances", instances)?;

    Ok(dict.into())
}

/// Convert an Office document to PDF
#[pyfunction]
#[pyo3(signature = (input_bytes, timeout_ms=None))]
fn convert_to_pdf(py: Python<'_>, input_bytes: &[u8], timeout_ms: Option<u64>) -> PyResult<PyObject> {
    let pool = get_global_pool()
        .ok_or_else(|| OfficePlaneError::ConnectionFailed("Pool not initialized".to_string()))?;

    let result = if let Some(timeout) = timeout_ms {
        pool.convert_with_timeout(input_bytes, timeout)
    } else {
        pool.convert(input_bytes)
    };

    match result {
        Ok(pdf_bytes) => Ok(PyBytes::new_bound(py, &pdf_bytes).into()),
        Err(e) => Err(e.into()),
    }
}

/// Render PDF to images
///
/// Returns a list of dicts with page info and base64-encoded image data
#[pyfunction]
#[pyo3(signature = (pdf_bytes, dpi=120, format="png", include_data=true))]
fn render_pdf(
    py: Python<'_>,
    pdf_bytes: &[u8],
    dpi: u32,
    format: &str,
    include_data: bool,
) -> PyResult<PyObject> {
    let fmt = ImageFormat_::from_str(format);

    let images = pdf_to_images(pdf_bytes, dpi, fmt)?;

    let result = PyList::empty_bound(py);
    for img in images {
        let dict = PyDict::new_bound(py);
        dict.set_item("page", img.page)?;
        dict.set_item("dpi", img.dpi)?;
        dict.set_item("width", img.width)?;
        dict.set_item("height", img.height)?;
        dict.set_item("sha256", &img.sha256)?;

        if include_data {
            if let Some(data) = img.data {
                dict.set_item("data", PyBytes::new_bound(py, &data))?;
            }
        }

        result.append(dict)?;
    }

    Ok(result.into())
}

/// Full render pipeline: convert + render in one call
///
/// This is the most efficient way to process a document as it avoids
/// crossing the Python/Rust boundary multiple times.
#[pyfunction]
#[pyo3(signature = (input_bytes, dpi=120, format="png", include_pdf=true, include_images=true, timeout_ms=None))]
fn render_document(
    py: Python<'_>,
    input_bytes: &[u8],
    dpi: u32,
    format: &str,
    include_pdf: bool,
    include_images: bool,
    timeout_ms: Option<u64>,
) -> PyResult<PyObject> {
    let start = Instant::now();

    let pool = get_global_pool()
        .ok_or_else(|| OfficePlaneError::ConnectionFailed("Pool not initialized".to_string()))?;

    // Convert to PDF
    let convert_start = Instant::now();
    let pdf_bytes = if let Some(timeout) = timeout_ms {
        pool.convert_with_timeout(input_bytes, timeout)?
    } else {
        pool.convert(input_bytes)?
    };
    let convert_ms = convert_start.elapsed().as_millis() as u64;

    // Calculate PDF hash
    let mut hasher = sha2::Sha256::new();
    Sha2Digest::update(&mut hasher, &pdf_bytes);
    let pdf_sha256 = hex::encode(hasher.finalize());

    // Render to images
    let render_start = Instant::now();
    let fmt = ImageFormat_::from_str(format);
    let images = pdf_to_images(&pdf_bytes, dpi, fmt)?;
    let render_ms = render_start.elapsed().as_millis() as u64;

    let total_ms = start.elapsed().as_millis() as u64;

    // Build response
    let result = PyDict::new_bound(py);

    // PDF info
    let pdf_dict = PyDict::new_bound(py);
    pdf_dict.set_item("sha256", &pdf_sha256)?;
    pdf_dict.set_item("size_bytes", pdf_bytes.len())?;
    if include_pdf {
        pdf_dict.set_item("data", PyBytes::new_bound(py, &pdf_bytes))?;
    }
    result.set_item("pdf", pdf_dict)?;

    // Pages
    let pages = PyList::empty_bound(py);
    for img in images {
        let dict = PyDict::new_bound(py);
        dict.set_item("page", img.page)?;
        dict.set_item("dpi", img.dpi)?;
        dict.set_item("width", img.width)?;
        dict.set_item("height", img.height)?;
        dict.set_item("sha256", &img.sha256)?;

        if include_images {
            if let Some(data) = img.data {
                dict.set_item("data", PyBytes::new_bound(py, &data))?;
            }
        }
        pages.append(dict)?;
    }
    result.set_item("pages", pages)?;

    // Timings
    let timings = PyDict::new_bound(py);
    timings.set_item("convert_ms", convert_ms)?;
    timings.set_item("render_ms", render_ms)?;
    timings.set_item("total_ms", total_ms)?;
    result.set_item("timings", timings)?;

    Ok(result.into())
}

/// Get version information
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// Python module definition
#[pymodule]
fn officeplane_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(init_pool, m)?)?;
    m.add_function(wrap_pyfunction!(pool_status, m)?)?;
    m.add_function(wrap_pyfunction!(convert_to_pdf, m)?)?;
    m.add_function(wrap_pyfunction!(render_pdf, m)?)?;
    m.add_function(wrap_pyfunction!(render_document, m)?)?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    Ok(())
}
