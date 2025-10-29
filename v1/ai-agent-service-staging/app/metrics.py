import asyncio
import os
import time
from functools import wraps

from agent_core.config.logging_config import logger

ENV = os.getenv("ENV")

if ENV != "DEVELOPMENT":
    from opentelemetry import metrics
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    # Setup OpenTelemetry metrics exporter (OTLP over gRPC)
    otlp_exporter = OTLPMetricExporter(endpoint="http://localhost:4317", insecure=True)
    reader = PeriodicExportingMetricReader(otlp_exporter, 60000)
    provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(provider)
    meter = metrics.get_meter("ai-service")

    execution_counter = meter.create_counter(
        "executions_total",
        description="Total number of function executions",
    )

    # Define histogram for execution timing (in seconds)
    execution_duration_hist = meter.create_histogram(
        name="execution_duration_seconds",
        unit="s",
        description="Time taken by function executions",
    )
else:
    logger.info("[METRICS] Development environment detected. Metrics disabled.")

    class _NoopCounter:
        def add(self, *_, **__):
            pass

    class _NoopHistogram:
        def record(self, *_, **__):
            pass

    class _NoopMeter:
        def create_counter(self, *_, **__):
            return _NoopCounter()

        def create_histogram(self, *_, **__):
            return _NoopHistogram()

    meter = _NoopMeter()

    execution_counter = meter.create_counter("executions_total")
    execution_duration_hist = meter.create_histogram("execution_duration_seconds")


def track_execution(operation_name):
    """Decorator that tracks function execution metrics if enabled."""

    if ENV == "DEVELOPMENT":
        def decorator(func):
            # Simply return original function without tracking
            return func
        return decorator

    logger.info(f"[METRICS] Setting up tracking for operation: {operation_name}")

    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                execution_counter.add(1, attributes={"operation": operation_name})
                try:
                    result = await func(*args, **kwargs)
                    duration = time.perf_counter() - start
                    execution_duration_hist.record(duration, {
                        "operation": operation_name,
                        "status": "success",
                    })
                    logger.info(
                        f"[METRICS] Successfully completed {operation_name} in {duration:.4f}s"
                    )
                    return result
                except Exception as e:
                    duration = time.perf_counter() - start
                    execution_duration_hist.record(duration, {
                        "operation": operation_name,
                        "status": "error",
                    })
                    logger.error(
                        f"[METRICS] Error in {operation_name} after {duration:.4f}s: {str(e)}",
                        exc_info=True,
                    )
                    raise

            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start = time.perf_counter()
                execution_counter.add(1, attributes={"operation": operation_name})
                try:
                    result = func(*args, **kwargs)
                    duration = time.perf_counter() - start
                    execution_duration_hist.record(duration, {
                        "operation": operation_name,
                        "status": "success",
                    })
                    logger.info(
                        f"[METRICS] Successfully completed {operation_name} in {duration:.4f}s"
                    )
                    return result
                except Exception as e:
                    duration = time.perf_counter() - start
                    execution_duration_hist.record(duration, {
                        "operation": operation_name,
                        "status": "error",
                    })
                    logger.error(
                        f"[METRICS] Error in {operation_name} after {duration:.4f}s: {str(e)}",
                        exc_info=True,
                    )
                    raise

            return sync_wrapper

    return decorator
