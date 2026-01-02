from prometheus_client import Counter, Histogram, Gauge

REQUESTS = Counter(
    "officeplane_requests_total",
    "Total HTTP requests",
    ["endpoint", "status", "ext"],
)

FAILURES = Counter(
    "officeplane_failures_total",
    "Total failures by stage/reason",
    ["stage", "reason"],
)

CONVERT_SECONDS = Histogram(
    "officeplane_convert_duration_seconds",
    "Office->PDF conversion duration",
)

RENDER_SECONDS = Histogram(
    "officeplane_render_duration_seconds",
    "PDF->images render duration",
)

TOTAL_SECONDS = Histogram(
    "officeplane_total_duration_seconds",
    "Total request duration",
)

POOL_READY = Gauge(
    "officeplane_pool_ready",
    "Number of LibreOffice instances ready",
)

INSTANCE_RESTARTS = Counter(
    "officeplane_instance_restarts_total",
    "LibreOffice instance restarts",
    ["port"],
)
