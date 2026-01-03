"""
Docker-based comparison test for Python vs Rust drivers.

This test requires Docker and runs both driver implementations
to verify they produce equivalent results.

Run with: pytest tests/test_driver_comparison.py -v -s
"""

import subprocess
import time
from pathlib import Path

import pytest
import httpx

TESTS_DIR = Path(__file__).parent
TEST_PPTX = TESTS_DIR / "test.pptx"

# Docker image names
PYTHON_IMAGE = "officeplane:python"
RUST_IMAGE = "officeplane:rust"

# Container settings
PYTHON_PORT = 8002
RUST_PORT = 8003


def is_docker_available() -> bool:
    """Check if Docker is available."""
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def image_exists(image_name: str) -> bool:
    """Check if a Docker image exists."""
    result = subprocess.run(
        ["docker", "images", "-q", image_name],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def wait_for_service(port: int, timeout: int = 60) -> bool:
    """Wait for service to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"http://localhost:{port}/health", timeout=2)
            if r.status_code == 200:
                return True
        except httpx.RequestError:
            pass
        time.sleep(1)
    return False


def render_document(port: int, file_path: Path) -> dict:
    """Render a document using the API."""
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/octet-stream")}
        r = httpx.post(
            f"http://localhost:{port}/render?dpi=120&output=both&inline=true",
            files=files,
            timeout=120,
        )
    r.raise_for_status()
    return r.json()


@pytest.fixture(scope="module")
def docker_containers():
    """Start both Docker containers for testing."""
    if not is_docker_available():
        pytest.skip("Docker not available")

    if not image_exists(PYTHON_IMAGE):
        pytest.skip(f"Docker image {PYTHON_IMAGE} not found. Build with: docker build -t {PYTHON_IMAGE} -f docker/Dockerfile .")

    if not image_exists(RUST_IMAGE):
        pytest.skip(f"Docker image {RUST_IMAGE} not found. Build with: docker build -t {RUST_IMAGE} -f docker/Dockerfile.rust .")

    containers = []

    # Start Python driver container
    print(f"\n🐍 Starting Python driver on port {PYTHON_PORT}...")
    python_container = subprocess.Popen(
        [
            "docker", "run", "--rm",
            "-p", f"{PYTHON_PORT}:8001",
            "--name", "officeplane-test-python",
            PYTHON_IMAGE,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    containers.append(("officeplane-test-python", python_container))

    # Start Rust driver container
    print(f"🦀 Starting Rust driver on port {RUST_PORT}...")
    rust_container = subprocess.Popen(
        [
            "docker", "run", "--rm",
            "-p", f"{RUST_PORT}:8001",
            "--name", "officeplane-test-rust",
            RUST_IMAGE,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    containers.append(("officeplane-test-rust", rust_container))

    # Wait for both services
    print("⏳ Waiting for services to be ready...")
    python_ready = wait_for_service(PYTHON_PORT, timeout=90)
    rust_ready = wait_for_service(RUST_PORT, timeout=90)

    if not python_ready or not rust_ready:
        # Cleanup on failure
        for name, _ in containers:
            subprocess.run(["docker", "stop", name], capture_output=True)
        pytest.fail(f"Services failed to start. Python: {python_ready}, Rust: {rust_ready}")

    print("✅ Both services ready!\n")

    yield {"python_port": PYTHON_PORT, "rust_port": RUST_PORT}

    # Cleanup
    print("\n🧹 Stopping containers...")
    for name, proc in containers:
        subprocess.run(["docker", "stop", name], capture_output=True)
        proc.wait()


@pytest.mark.skipif(not TEST_PPTX.exists(), reason="test.pptx not found")
def test_driver_comparison(docker_containers):
    """Compare Python and Rust driver outputs."""
    python_port = docker_containers["python_port"]
    rust_port = docker_containers["rust_port"]

    print(f"📄 Testing with: {TEST_PPTX.name}")
    print("-" * 60)

    # Render with Python driver
    print("\n🐍 Python driver:")
    start = time.time()
    python_result = render_document(python_port, TEST_PPTX)
    python_time = time.time() - start
    print(f"   Time: {python_time:.2f}s")
    print(f"   Pages: {python_result['manifest']['pages_count']}")
    print(f"   PDF size: {python_result['pdf']['size_bytes']} bytes")

    # Render with Rust driver
    print("\n🦀 Rust driver:")
    start = time.time()
    rust_result = render_document(rust_port, TEST_PPTX)
    rust_time = time.time() - start
    print(f"   Time: {rust_time:.2f}s")
    print(f"   Pages: {rust_result['manifest']['pages_count']}")
    print(f"   PDF size: {rust_result['pdf']['size_bytes']} bytes")

    # Compare results
    print("\n📊 Comparison:")
    print("-" * 60)

    # Both should have same page count
    assert python_result["manifest"]["pages_count"] == rust_result["manifest"]["pages_count"], \
        "Page counts differ!"

    pages_count = python_result["manifest"]["pages_count"]
    print(f"   ✅ Page count matches: {pages_count}")

    # Both should produce valid PDFs
    assert python_result["pdf"]["size_bytes"] > 0, "Python PDF is empty"
    assert rust_result["pdf"]["size_bytes"] > 0, "Rust PDF is empty"
    print("   ✅ Both produced valid PDFs")

    # Compare page dimensions (should be similar)
    for i in range(pages_count):
        py_page = python_result["pages"][i]
        rs_page = rust_result["pages"][i]

        assert py_page["page"] == rs_page["page"], f"Page numbers differ at index {i}"
        assert py_page["dpi"] == rs_page["dpi"], f"DPI differs for page {i}"

        # Dimensions should be very close (within 1% due to potential rounding)
        width_diff = abs(py_page["width"] - rs_page["width"]) / py_page["width"]
        height_diff = abs(py_page["height"] - rs_page["height"]) / py_page["height"]

        assert width_diff < 0.01, f"Width differs too much for page {i}"
        assert height_diff < 0.01, f"Height differs too much for page {i}"

    print("   ✅ Page dimensions match")

    # Performance comparison
    speedup = python_time / rust_time if rust_time > 0 else 0
    print("\n⚡ Performance:")
    print(f"   Python: {python_time:.2f}s")
    print(f"   Rust:   {rust_time:.2f}s")
    if speedup > 1:
        print(f"   Rust is {speedup:.1f}x faster")
    elif speedup < 1 and speedup > 0:
        print(f"   Python is {1/speedup:.1f}x faster")
    else:
        print("   Similar performance")

    print("\n✅ All comparisons passed!")


@pytest.mark.skipif(not TEST_PPTX.exists(), reason="test.pptx not found")
def test_multiple_renders_performance(docker_containers):
    """Test multiple renders to get better performance data."""
    rust_port = docker_containers["rust_port"]
    python_port = docker_containers["python_port"]

    iterations = 3
    print(f"\n🔄 Running {iterations} iterations for performance comparison...")
    print("-" * 60)

    python_times = []
    rust_times = []

    for i in range(iterations):
        # Python
        start = time.time()
        render_document(python_port, TEST_PPTX)
        python_times.append(time.time() - start)

        # Rust
        start = time.time()
        render_document(rust_port, TEST_PPTX)
        rust_times.append(time.time() - start)

        print(f"   Iteration {i+1}: Python={python_times[-1]:.2f}s, Rust={rust_times[-1]:.2f}s")

    avg_python = sum(python_times) / len(python_times)
    avg_rust = sum(rust_times) / len(rust_times)

    print(f"\n📊 Average over {iterations} iterations:")
    print(f"   Python: {avg_python:.2f}s")
    print(f"   Rust:   {avg_rust:.2f}s")

    if avg_rust > 0:
        speedup = avg_python / avg_rust
        if speedup > 1:
            print(f"   🦀 Rust is {speedup:.1f}x faster on average")
        else:
            print(f"   🐍 Python is {1/speedup:.1f}x faster on average")
