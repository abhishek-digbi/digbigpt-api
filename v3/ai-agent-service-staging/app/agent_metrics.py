"""Agent metrics tracking with OpenTelemetry."""
from functools import wraps
import time
from typing import Any, Callable

# Import meter and logger from the main metrics module to avoid duplicate setup
from app.metrics import meter
from agent_core.config.logging_config import logger

# Get the meter for agent-specific metrics
agent_meter = meter

# Create metrics
agent_run_counter = agent_meter.create_counter(
    "agent_runs_total",
    description="Total number of agent runs",
)

agent_fail_counter = agent_meter.create_counter(
    "agent_run_failures_total",
    description="Total number of failed agent runs",
)

agent_duration_hist = agent_meter.create_histogram(
    "agent_duration_seconds",
    unit="s",
    description="Time taken by agent execution",
)


def track_agent_metrics(agent_id_arg: str = 'agent_id') -> Callable:
    """Simplified decorator to track agent execution metrics."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Simple agent ID extraction
            agent_id = 'unknown'
            if agent_id_arg in kwargs:
                agent_id = str(kwargs[agent_id_arg])
            elif len(args) > 1:  # Assuming agent_id is the second argument
                agent_id = str(args[1])

            logger.debug(f"[METRICS] Starting agent execution: {agent_id}")
            start_time = time.perf_counter()

            try:
                result = await func(*args, **kwargs)
                duration = time.perf_counter() - start_time

                # Record success
                agent_run_counter.add(1, attributes={"agent_id": agent_id})
                agent_duration_hist.record(duration, attributes={"agent_id": agent_id})
                logger.info(f"[METRICS] Agent {agent_id} completed successfully in {duration:.4f}s")

                return result

            except Exception as e:
                duration = time.perf_counter() - start_time
                error_type = type(e).__name__

                # Record failure
                agent_fail_counter.add(1, attributes={
                    "agent_id": agent_id,
                    "error_type": error_type
                })
                agent_duration_hist.record(duration, attributes={"agent_id": agent_id})

                logger.error(
                    f"[METRICS] Agent {agent_id} failed after {duration:.4f}s: {error_type}",
                    exc_info=True,
                    extra={"error_type": error_type, "agent_id": agent_id, "duration": duration}
                )
                raise

        return wrapper
    return decorator
