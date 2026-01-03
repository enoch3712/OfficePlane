//! LibreOffice connection pool manager
//!
//! Manages a pool of LibreOffice instances for high-throughput conversion.
//! Uses a lock-free queue for instance acquisition.

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use crossbeam::queue::ArrayQueue;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use tracing::info;

use crate::error::{OfficePlaneError, Result};
use crate::uno::LibreOfficeInstance;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InstanceStatus {
    pub port: u16,
    pub ready: bool,
    pub restarts: u64,
    pub last_error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoolStatus {
    pub total: usize,
    pub ready: usize,
    pub instances: Vec<InstanceStatus>,
}

/// High-performance LibreOffice instance pool
pub struct LibreOfficePool {
    instances: Vec<Arc<LibreOfficeInstance>>,
    queue: Arc<ArrayQueue<Arc<LibreOfficeInstance>>>,
    size: usize,
    ready_count: AtomicUsize,
    convert_timeout_secs: u64,
}

impl LibreOfficePool {
    /// Create a new pool with the specified size
    pub fn new(size: usize, start_port: u16, convert_timeout_secs: u64) -> Self {
        let instances: Vec<Arc<LibreOfficeInstance>> = (0..size)
            .map(|i| Arc::new(LibreOfficeInstance::new(start_port + i as u16)))
            .collect();

        let queue = Arc::new(ArrayQueue::new(size));

        Self {
            instances,
            queue,
            size,
            ready_count: AtomicUsize::new(0),
            convert_timeout_secs,
        }
    }

    /// Start all instances asynchronously
    pub fn start_all_async(&self) {
        let instances = self.instances.clone();
        let queue = self.queue.clone();
        let ready_count = &self.ready_count as *const AtomicUsize as usize;

        thread::spawn(move || {
            let ready_count = unsafe { &*(ready_count as *const AtomicUsize) };

            for inst in instances {
                if inst.start().is_ok() && inst.is_ready() {
                    ready_count.fetch_add(1, Ordering::SeqCst);
                }
                let _ = queue.push(inst);
                thread::sleep(Duration::from_millis(200));
            }
            info!("Pool warmup complete");
        });
    }

    /// Start all instances synchronously (blocking)
    pub fn start_all_sync(&self) -> Result<()> {
        for inst in &self.instances {
            inst.start()?;
            if inst.is_ready() {
                self.ready_count.fetch_add(1, Ordering::SeqCst);
            }
            let _ = self.queue.push(inst.clone());
        }
        Ok(())
    }

    /// Get pool status
    pub fn status(&self) -> PoolStatus {
        PoolStatus {
            total: self.size,
            ready: self.ready_count.load(Ordering::SeqCst),
            instances: self
                .instances
                .iter()
                .map(|inst| InstanceStatus {
                    port: inst.port,
                    ready: inst.is_ready(),
                    restarts: inst.restart_count(),
                    last_error: inst.last_error(),
                })
                .collect(),
        }
    }

    /// Convert a document to PDF using an available instance
    pub fn convert(&self, input_bytes: &[u8]) -> Result<Vec<u8>> {
        // Get an instance from the queue (non-blocking)
        let inst = self
            .queue
            .pop()
            .ok_or(OfficePlaneError::PoolExhausted)?;

        let result = inst.convert_to_pdf(input_bytes, self.convert_timeout_secs);

        // Return instance to pool
        let _ = self.queue.push(inst);

        result
    }

    /// Convert with a timeout for acquiring an instance
    pub fn convert_with_timeout(&self, input_bytes: &[u8], acquire_timeout_ms: u64) -> Result<Vec<u8>> {
        let start = std::time::Instant::now();
        let timeout = Duration::from_millis(acquire_timeout_ms);

        loop {
            if let Some(inst) = self.queue.pop() {
                let result = inst.convert_to_pdf(input_bytes, self.convert_timeout_secs);
                let _ = self.queue.push(inst);
                return result;
            }

            if start.elapsed() > timeout {
                return Err(OfficePlaneError::PoolExhausted);
            }

            thread::sleep(Duration::from_millis(10));
        }
    }

    pub fn ready_count(&self) -> usize {
        self.ready_count.load(Ordering::SeqCst)
    }
}

/// Global pool singleton for the Python bindings
static GLOBAL_POOL: RwLock<Option<Arc<LibreOfficePool>>> = RwLock::new(None);

pub fn init_global_pool(size: usize, start_port: u16, timeout_secs: u64) {
    let pool = Arc::new(LibreOfficePool::new(size, start_port, timeout_secs));
    pool.start_all_async();
    *GLOBAL_POOL.write() = Some(pool);
}

pub fn get_global_pool() -> Option<Arc<LibreOfficePool>> {
    GLOBAL_POOL.read().clone()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pool_creation() {
        let pool = LibreOfficePool::new(2, 3000, 45);
        assert_eq!(pool.size, 2);
        assert_eq!(pool.ready_count(), 0);
    }
}
