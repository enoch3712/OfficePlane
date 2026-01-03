//! PDF to image rendering using MuPDF
//!
//! High-performance parallel rendering of PDF pages to images.
//! Uses native MuPDF bindings for maximum speed.

use image::codecs::jpeg::JpegEncoder;
use image::codecs::png::PngEncoder;
use image::{ColorType, ImageEncoder};
use mupdf::{Colorspace, Document, Matrix};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tracing::debug;

use crate::error::{OfficePlaneError, Result};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PageImage {
    pub page: usize,
    pub dpi: u32,
    pub width: u32,
    pub height: u32,
    pub sha256: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<Vec<u8>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ImageFormat_ {
    Png,
    Jpeg,
}

impl ImageFormat_ {
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "jpeg" | "jpg" => Self::Jpeg,
            _ => Self::Png,
        }
    }

    pub fn extension(&self) -> &'static str {
        match self {
            Self::Png => "png",
            Self::Jpeg => "jpeg",
        }
    }
}

/// Render a single PDF page to an image
fn render_page(
    doc: &Document,
    page_num: i32,
    dpi: u32,
    format: ImageFormat_,
) -> Result<PageImage> {
    let page = doc
        .load_page(page_num)
        .map_err(|e| OfficePlaneError::RenderFailed(format!("Failed to load page {}: {}", page_num, e)))?;

    let zoom = dpi as f32 / 72.0;
    let matrix = Matrix::new_scale(zoom, zoom);

    let pixmap = page
        .to_pixmap(&matrix, &Colorspace::device_rgb(), 1.0, false)
        .map_err(|e| OfficePlaneError::RenderFailed(format!("Failed to render page {}: {}", page_num, e)))?;

    let width = pixmap.width() as u32;
    let height = pixmap.height() as u32;
    let samples = pixmap.samples().to_vec();

    // Encode to format
    let data = match format {
        ImageFormat_::Png => {
            let mut buffer = Vec::new();
            let encoder = PngEncoder::new(&mut buffer);
            encoder
                .write_image(&samples, width, height, ColorType::Rgb8.into())
                .map_err(|e| OfficePlaneError::RenderFailed(e.to_string()))?;
            buffer
        }
        ImageFormat_::Jpeg => {
            let mut buffer = Vec::new();
            let encoder = JpegEncoder::new_with_quality(&mut buffer, 90);
            encoder
                .write_image(&samples, width, height, ColorType::Rgb8.into())
                .map_err(|e| OfficePlaneError::RenderFailed(e.to_string()))?;
            buffer
        }
    };

    // Calculate SHA256
    let mut hasher = Sha256::new();
    hasher.update(&data);
    let sha256 = hex::encode(hasher.finalize());

    Ok(PageImage {
        page: (page_num + 1) as usize, // 1-indexed
        dpi,
        width,
        height,
        sha256,
        data: Some(data),
    })
}

/// Render all pages of a PDF to images (parallel)
pub fn pdf_to_images(pdf_bytes: &[u8], dpi: u32, format: ImageFormat_) -> Result<Vec<PageImage>> {
    let doc = Document::from_bytes(pdf_bytes, "application/pdf")
        .map_err(|e| OfficePlaneError::RenderFailed(format!("Failed to open PDF: {}", e)))?;

    let page_count = doc.page_count()
        .map_err(|e| OfficePlaneError::RenderFailed(format!("Failed to get page count: {}", e)))?;

    debug!(pages = page_count, dpi = dpi, "Rendering PDF");

    // Render pages in parallel using rayon
    // Note: MuPDF Document is not Send, so we need to reload for each thread
    let pdf_bytes = pdf_bytes.to_vec();
    let results: Vec<Result<PageImage>> = (0..page_count)
        .into_par_iter()
        .map(|page_num| {
            let doc = Document::from_bytes(&pdf_bytes, "application/pdf")
                .map_err(|e| OfficePlaneError::RenderFailed(format!("Failed to open PDF: {}", e)))?;
            render_page(&doc, page_num, dpi, format)
        })
        .collect();

    // Collect results, propagating any errors
    results.into_iter().collect()
}

/// Render pages sequentially (for when parallel isn't beneficial)
pub fn pdf_to_images_sequential(pdf_bytes: &[u8], dpi: u32, format: ImageFormat_) -> Result<Vec<PageImage>> {
    let doc = Document::from_bytes(pdf_bytes, "application/pdf")
        .map_err(|e| OfficePlaneError::RenderFailed(format!("Failed to open PDF: {}", e)))?;

    let page_count = doc.page_count()
        .map_err(|e| OfficePlaneError::RenderFailed(format!("Failed to get page count: {}", e)))?;

    let mut images = Vec::with_capacity(page_count as usize);
    for page_num in 0..page_count {
        images.push(render_page(&doc, page_num, dpi, format)?);
    }

    Ok(images)
}

/// Get PDF info without rendering
pub fn pdf_info(pdf_bytes: &[u8]) -> Result<(usize, String)> {
    let doc = Document::from_bytes(pdf_bytes, "application/pdf")
        .map_err(|e| OfficePlaneError::RenderFailed(format!("Failed to open PDF: {}", e)))?;

    let page_count = doc.page_count()
        .map_err(|e| OfficePlaneError::RenderFailed(e.to_string()))?;

    // Calculate SHA256 of PDF
    let mut hasher = Sha256::new();
    hasher.update(pdf_bytes);
    let sha256 = hex::encode(hasher.finalize());

    Ok((page_count as usize, sha256))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_image_format() {
        assert_eq!(ImageFormat_::from_str("png"), ImageFormat_::Png);
        assert_eq!(ImageFormat_::from_str("jpeg"), ImageFormat_::Jpeg);
        assert_eq!(ImageFormat_::from_str("JPEG"), ImageFormat_::Jpeg);
    }
}
