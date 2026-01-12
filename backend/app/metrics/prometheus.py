"""
Prometheus Metrics Collection for VAS-MS-V2

Metrics exported:
- vas_streams_total{state} - Total streams by state
- vas_producers_total{state} - Total producers by state
- vas_consumers_total{state} - Total consumers by state
- vas_stream_uptime_seconds{stream_id} - Stream uptime
- vas_ffmpeg_process_cpu_percent{stream_id} - FFmpeg CPU usage
- vas_ffmpeg_process_memory_mb{stream_id} - FFmpeg memory usage
- vas_consumer_session_duration_seconds{stream_id} - Average consumer session duration
- vas_api_request_duration_seconds{endpoint, method} - API request latency
"""
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST
)
from typing import Dict, Any
from loguru import logger

# Create a custom registry for VAS metrics
vas_registry = CollectorRegistry()

# Stream metrics
vas_streams_total = Gauge(
    "vas_streams_total",
    "Total number of streams by state",
    ["state"],
    registry=vas_registry
)

vas_stream_uptime_seconds = Gauge(
    "vas_stream_uptime_seconds",
    "Stream uptime in seconds",
    ["stream_id", "stream_name"],
    registry=vas_registry
)

# Producer metrics
vas_producers_total = Gauge(
    "vas_producers_total",
    "Total number of producers by state",
    ["state"],
    registry=vas_registry
)

vas_producer_uptime_seconds = Gauge(
    "vas_producer_uptime_seconds",
    "Producer uptime in seconds",
    ["producer_id", "stream_id"],
    registry=vas_registry
)

# Consumer metrics
vas_consumers_total = Gauge(
    "vas_consumers_total",
    "Total number of consumers by state",
    ["state"],
    registry=vas_registry
)

vas_consumer_session_duration_seconds = Gauge(
    "vas_consumer_session_duration_seconds",
    "Consumer session duration in seconds",
    ["consumer_id", "stream_id", "client_id"],
    registry=vas_registry
)

vas_active_consumers = Gauge(
    "vas_active_consumers",
    "Number of active consumers per stream",
    ["stream_id"],
    registry=vas_registry
)

# FFmpeg metrics
vas_ffmpeg_process_cpu_percent = Gauge(
    "vas_ffmpeg_process_cpu_percent",
    "FFmpeg process CPU usage percentage",
    ["stream_id"],
    registry=vas_registry
)

vas_ffmpeg_process_memory_mb = Gauge(
    "vas_ffmpeg_process_memory_mb",
    "FFmpeg process memory usage in MB",
    ["stream_id"],
    registry=vas_registry
)

vas_ffmpeg_processes_healthy = Gauge(
    "vas_ffmpeg_processes_healthy",
    "Number of healthy FFmpeg processes",
    registry=vas_registry
)

# API metrics
vas_api_request_duration_seconds = Histogram(
    "vas_api_request_duration_seconds",
    "API request latency in seconds",
    ["endpoint", "method", "status_code"],
    registry=vas_registry,
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

vas_api_requests_total = Counter(
    "vas_api_requests_total",
    "Total number of API requests",
    ["endpoint", "method", "status_code"],
    registry=vas_registry
)

# System info
vas_info = Info(
    "vas_ms_v2",
    "VAS-MS-V2 system information",
    registry=vas_registry
)


class MetricsCollector:
    """
    Collects and updates Prometheus metrics from VAS services.
    """

    def __init__(self):
        """Initialize metrics collector."""
        logger.info("MetricsCollector initialized")

    async def update_stream_metrics(self, stream_counts: Dict[str, int]):
        """
        Update stream count metrics.

        Args:
            stream_counts: Dict of {state: count}
        """
        for state, count in stream_counts.items():
            vas_streams_total.labels(state=state).set(count)

    async def update_stream_uptime(self, stream_id: str, stream_name: str, uptime_seconds: int):
        """
        Update stream uptime metric.

        Args:
            stream_id: Stream UUID
            stream_name: Stream name
            uptime_seconds: Uptime in seconds
        """
        vas_stream_uptime_seconds.labels(
            stream_id=stream_id,
            stream_name=stream_name
        ).set(uptime_seconds)

    async def update_producer_metrics(self, producer_counts: Dict[str, int]):
        """
        Update producer count metrics.

        Args:
            producer_counts: Dict of {state: count}
        """
        for state, count in producer_counts.items():
            vas_producers_total.labels(state=state).set(count)

    async def update_consumer_metrics(self, consumer_counts: Dict[str, int]):
        """
        Update consumer count metrics.

        Args:
            consumer_counts: Dict of {state: count}
        """
        for state, count in consumer_counts.items():
            vas_consumers_total.labels(state=state).set(count)

    async def update_ffmpeg_metrics(self, stream_id: str, cpu_percent: float, memory_mb: float):
        """
        Update FFmpeg process metrics.

        Args:
            stream_id: Stream UUID
            cpu_percent: CPU usage percentage
            memory_mb: Memory usage in MB
        """
        vas_ffmpeg_process_cpu_percent.labels(stream_id=stream_id).set(cpu_percent)
        vas_ffmpeg_process_memory_mb.labels(stream_id=stream_id).set(memory_mb)

    async def update_ffmpeg_health_count(self, healthy_count: int):
        """
        Update count of healthy FFmpeg processes.

        Args:
            healthy_count: Number of healthy processes
        """
        vas_ffmpeg_processes_healthy.set(healthy_count)

    async def update_consumer_session(
        self,
        consumer_id: str,
        stream_id: str,
        client_id: str,
        duration_seconds: int
    ):
        """
        Update consumer session duration metric.

        Args:
            consumer_id: Consumer UUID
            stream_id: Stream UUID
            client_id: Client identifier
            duration_seconds: Session duration in seconds
        """
        vas_consumer_session_duration_seconds.labels(
            consumer_id=consumer_id,
            stream_id=stream_id,
            client_id=client_id
        ).set(duration_seconds)

    async def update_active_consumers_per_stream(self, stream_id: str, count: int):
        """
        Update active consumer count per stream.

        Args:
            stream_id: Stream UUID
            count: Number of active consumers
        """
        vas_active_consumers.labels(stream_id=stream_id).set(count)

    def record_api_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_seconds: float
    ):
        """
        Record API request metrics.

        Args:
            endpoint: API endpoint path
            method: HTTP method
            status_code: HTTP status code
            duration_seconds: Request duration in seconds
        """
        vas_api_requests_total.labels(
            endpoint=endpoint,
            method=method,
            status_code=status_code
        ).inc()

        vas_api_request_duration_seconds.labels(
            endpoint=endpoint,
            method=method,
            status_code=status_code
        ).observe(duration_seconds)

    def set_system_info(self, version: str, environment: str):
        """
        Set VAS system information.

        Args:
            version: VAS version
            environment: Environment (dev, staging, production)
        """
        vas_info.info({
            "version": version,
            "environment": environment,
            "service": "vas-ms-v2"
        })


# Global metrics collector instance
metrics_collector = MetricsCollector()


def get_prometheus_metrics() -> bytes:
    """
    Get Prometheus metrics in text format.

    Returns:
        Prometheus metrics as bytes
    """
    return generate_latest(vas_registry)


def get_prometheus_content_type() -> str:
    """
    Get Prometheus content type header.

    Returns:
        Content type string
    """
    return CONTENT_TYPE_LATEST
