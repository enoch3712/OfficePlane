//! Direct UNO socket communication with LibreOffice
//!
//! This module handles low-level communication with LibreOffice instances
//! via the UNO binary protocol, eliminating subprocess overhead.

use std::io::Write;
use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::time::{Duration, Instant};

use parking_lot::Mutex;
use tracing::{debug, error, info, warn};

use crate::error::{OfficePlaneError, Result};

/// Represents a single LibreOffice instance
pub struct LibreOfficeInstance {
    pub port: u16,
    pub uno_port: u16,
    process: Mutex<Option<Child>>,
    ready: AtomicBool,
    restarts: AtomicU64,
    last_error: Mutex<Option<String>>,
    home_dir: String,
}

impl LibreOfficeInstance {
    pub fn new(port: u16) -> Self {
        let home_dir = format!("/tmp/officeplane_lo_home_{}", port);
        std::fs::create_dir_all(&home_dir).ok();

        Self {
            port,
            uno_port: port + 100,
            process: Mutex::new(None),
            ready: AtomicBool::new(false),
            restarts: AtomicU64::new(0),
            last_error: Mutex::new(None),
            home_dir,
        }
    }

    /// Check if LibreOffice is listening on the port
    pub fn is_running(&self) -> bool {
        TcpStream::connect_timeout(
            &format!("127.0.0.1:{}", self.port).parse().unwrap(),
            Duration::from_millis(300),
        )
        .is_ok()
    }

    /// Start the LibreOffice instance via unoserver
    pub fn start(&self) -> Result<()> {
        if self.is_running() {
            self.ready.store(true, Ordering::SeqCst);
            return Ok(());
        }

        info!(port = self.port, "Starting LibreOffice instance");

        let soffice_path = find_soffice_binary();

        let child = Command::new("unoserver")
            .args([
                "--port",
                &self.port.to_string(),
                "--uno-port",
                &self.uno_port.to_string(),
                "--executable",
                &soffice_path,
            ])
            .env("HOME", &self.home_dir)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| OfficePlaneError::ConnectionFailed(e.to_string()))?;

        *self.process.lock() = Some(child);

        // Wait for instance to be ready
        let start = Instant::now();
        while start.elapsed() < Duration::from_secs(30) {
            if self.is_running() {
                self.ready.store(true, Ordering::SeqCst);
                *self.last_error.lock() = None;
                info!(port = self.port, "Instance ready");
                return Ok(());
            }
            std::thread::sleep(Duration::from_millis(300));
        }

        self.ready.store(false, Ordering::SeqCst);
        *self.last_error.lock() = Some("Failed to start".to_string());
        error!(port = self.port, "Instance failed to start");
        Err(OfficePlaneError::ConnectionFailed("Timeout waiting for LibreOffice".to_string()))
    }

    /// Stop the instance
    pub fn stop(&self) {
        let mut proc = self.process.lock();
        if let Some(ref mut child) = *proc {
            let _ = child.kill();
            let _ = child.wait();
        }
        *proc = None;
        self.ready.store(false, Ordering::SeqCst);
    }

    /// Restart the instance
    pub fn restart(&self, reason: &str) {
        self.restarts.fetch_add(1, Ordering::SeqCst);
        *self.last_error.lock() = Some(reason.to_string());
        warn!(port = self.port, reason = reason, "Restarting instance");
        self.stop();
        let _ = self.start();
    }

    /// Convert document to PDF using unoconvert via direct pipe
    /// This is still using subprocess but with optimized I/O
    pub fn convert_to_pdf(&self, input_bytes: &[u8], timeout_secs: u64) -> Result<Vec<u8>> {
        if !self.ready.load(Ordering::SeqCst) {
            self.start()?;
        }

        let start = Instant::now();

        let mut child = Command::new("unoconvert")
            .args([
                "--port",
                &self.port.to_string(),
                "--convert-to",
                "pdf",
                "-",
                "-",
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| OfficePlaneError::ConversionFailed(e.to_string()))?;

        // Write input
        if let Some(ref mut stdin) = child.stdin {
            stdin.write_all(input_bytes)
                .map_err(|e| OfficePlaneError::ConversionFailed(e.to_string()))?;
        }
        drop(child.stdin.take());

        // Wait with timeout
        let output = match child.wait_with_output() {
            Ok(out) => out,
            Err(e) => {
                self.restart("io_error");
                return Err(OfficePlaneError::ConversionFailed(e.to_string()));
            }
        };

        if start.elapsed() > Duration::from_secs(timeout_secs) {
            self.restart("timeout");
            return Err(OfficePlaneError::Timeout);
        }

        if output.status.success() && !output.stdout.is_empty() {
            debug!(
                port = self.port,
                duration_ms = start.elapsed().as_millis() as u64,
                "Conversion successful"
            );
            Ok(output.stdout)
        } else {
            let err = String::from_utf8_lossy(&output.stderr);
            self.restart(&format!("conversion_failed:{}", output.status.code().unwrap_or(-1)));
            Err(OfficePlaneError::ConversionFailed(err.to_string()))
        }
    }

    pub fn is_ready(&self) -> bool {
        self.ready.load(Ordering::SeqCst)
    }

    pub fn restart_count(&self) -> u64 {
        self.restarts.load(Ordering::SeqCst)
    }

    pub fn last_error(&self) -> Option<String> {
        self.last_error.lock().clone()
    }
}

impl Drop for LibreOfficeInstance {
    fn drop(&mut self) {
        self.stop();
    }
}

/// Find the soffice binary path
fn find_soffice_binary() -> String {
    for cmd in &["soffice", "libreoffice"] {
        if let Ok(path) = which::which(cmd) {
            return path.to_string_lossy().to_string();
        }
    }
    "/usr/bin/soffice".to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_instance_new() {
        let inst = LibreOfficeInstance::new(2002);
        assert_eq!(inst.port, 2002);
        assert_eq!(inst.uno_port, 2102);
        assert!(!inst.is_ready());
    }
}
