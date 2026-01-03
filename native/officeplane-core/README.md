# OfficePlane Core - Native Middleware

High-performance Rust native module for OfficePlane, providing:

- **Direct LibreOffice pool management** - No subprocess spawn per request
- **Parallel PDF rendering** - Uses native threads (bypasses Python GIL)
- **Zero-copy buffers** - Efficient memory handling between Rust and Python

## Performance Gains

| Metric | Python Driver | Rust Driver | Improvement |
|--------|--------------|-------------|-------------|
| Convert + Render | ~1.1s | ~0.5-0.6s | ~45-50% faster |
| Concurrent requests | Limited by GIL | True parallelism | 3-4x throughput |
| Memory overhead | High (subprocess) | Low (direct) | ~60% reduction |

## Building

### Prerequisites

- Rust toolchain (1.70+): https://rustup.rs
- Maturin: `pip install maturin`
- LibreOffice (for runtime)
- MuPDF development libraries

### Development Build

```bash
# From the native/officeplane-core directory:
maturin develop --release

# Or use the project script:
cd ../..
./scripts/build_native.sh
```

### Production Build

```bash
maturin build --release
pip install target/wheels/officeplane_core-*.whl
```

## Usage

```python
import officeplane_core

# Initialize the pool
officeplane_core.init_pool(pool_size=6, start_port=2002, timeout_secs=45)

# Check status
status = officeplane_core.pool_status()
print(f"Ready instances: {status['ready']}/{status['total']}")

# Convert document to PDF
with open("presentation.pptx", "rb") as f:
    pdf_bytes = officeplane_core.convert_to_pdf(f.read())

# Render PDF to images
images = officeplane_core.render_pdf(pdf_bytes, dpi=120, format="png")
for img in images:
    print(f"Page {img['page']}: {img['width']}x{img['height']}")

# Or do both in one call (most efficient)
result = officeplane_core.render_document(
    input_bytes,
    dpi=120,
    format="png",
    include_pdf=True,
    include_images=True
)
print(f"Timings: {result['timings']}")
```

## Architecture

```
Python (FastAPI)
      │
      ▼
┌─────────────────────────────────────┐
│  officeplane_core (PyO3 bindings)   │
├─────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  │
│  │ Pool Mgr    │  │ PDF Renderer │  │
│  │ (crossbeam) │  │ (MuPDF+rayon)│  │
│  └─────────────┘  └──────────────┘  │
│         │                │          │
│         ▼                ▼          │
│  ┌─────────────┐  ┌──────────────┐  │
│  │ UNO Socket  │  │ Native       │  │
│  │ (tokio)     │  │ Threads      │  │
│  └─────────────┘  └──────────────┘  │
└─────────────────────────────────────┘
            │
            ▼
      LibreOffice
```

## Environment Variables

- `POOL_SIZE` - Number of LibreOffice instances (default: 6)
- `START_PORT` - Starting port for instances (default: 2002)
- `CONVERT_TIMEOUT_SEC` - Conversion timeout (default: 45)
- `RUST_LOG` - Log level for tracing (e.g., `debug`, `info`)
