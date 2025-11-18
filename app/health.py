"""
Health check endpoints for liveness and readiness probes.
"""
from datetime import datetime
from typing import Dict, Any
import psutil
from .config import get_settings
from .logging import get_logger

logger = get_logger()


class HealthChecker:
    """
    Health checker for EventBridge service.

    Provides:
    - Liveness checks (is the service running?)
    - Readiness checks (can the service handle traffic?)
    """

    def __init__(self, service_name: str = "eventbridge", version: str = "0.1.0"):
        self.service_name = service_name
        self.version = version
        self.settings = get_settings()

    def liveness(self) -> Dict[str, Any]:
        """
        Liveness check - basic health check.

        Returns:
            dict: Health status with service info and timestamp
        """
        return {
            "status": "ok",
            "service": self.service_name,
            "version": self.version,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    async def readiness(self) -> Dict[str, Any]:
        """
        Readiness check - comprehensive health check.

        Checks:
        - Redis connectivity (if configured)
        - Disk space availability
        - Memory availability
        - System resources

        Returns:
            dict: Readiness status with detailed check results
        """
        checks = {}
        overall_status = "ready"

        # Check Redis connectivity
        redis_check = await self._check_redis()
        checks["redis"] = redis_check
        if redis_check["status"] == "error":
            overall_status = "not_ready"

        # Check disk space
        disk_check = self._check_disk_space()
        checks["disk_space"] = disk_check
        if disk_check["status"] in ["error", "warning"]:
            if disk_check["status"] == "error":
                overall_status = "not_ready"

        # Check memory
        memory_check = self._check_memory()
        checks["memory"] = memory_check
        if memory_check["status"] in ["error", "warning"]:
            if memory_check["status"] == "error":
                overall_status = "not_ready"

        return {
            "status": overall_status,
            "service": self.service_name,
            "version": self.version,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "checks": checks,
        }

    async def _check_redis(self) -> Dict[str, Any]:
        """
        Check Redis connectivity.

        Returns:
            dict: Redis health check result
        """
        if not self.settings.REDIS_URL:
            return {
                "status": "skipped",
                "message": "Redis not configured",
            }

        try:
            import redis
            import time

            # Parse Redis URL
            redis_url = str(self.settings.REDIS_URL)

            # Connect to Redis
            start = time.time()
            client = redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
            client.ping()
            latency_ms = round((time.time() - start) * 1000, 2)

            return {
                "status": "ok",
                "latency_ms": latency_ms,
            }

        except Exception as e:
            logger.warning("redis_health_check_failed", error=str(e))
            return {
                "status": "error",
                "error": str(e),
            }

    def _check_disk_space(self, threshold_gb: float = 1.0) -> Dict[str, Any]:
        """
        Check available disk space.

        Args:
            threshold_gb: Minimum available disk space in GB (default: 1.0)

        Returns:
            dict: Disk space health check result
        """
        try:
            disk = psutil.disk_usage("/")
            available_gb = disk.free / (1024**3)

            if available_gb < threshold_gb:
                status = "error"
            elif available_gb < threshold_gb * 2:
                status = "warning"
            else:
                status = "ok"

            return {
                "status": status,
                "available_gb": round(available_gb, 2),
                "total_gb": round(disk.total / (1024**3), 2),
                "used_percent": disk.percent,
            }

        except Exception as e:
            logger.warning("disk_health_check_failed", error=str(e))
            return {
                "status": "error",
                "error": str(e),
            }

    def _check_memory(self, threshold_mb: float = 50.0) -> Dict[str, Any]:
        """
        Check available memory.

        Args:
            threshold_mb: Minimum available memory in MB (default: 50.0)

        Returns:
            dict: Memory health check result
        """
        try:
            memory = psutil.virtual_memory()
            available_mb = memory.available / (1024**2)

            if available_mb < threshold_mb:
                status = "error"
            elif available_mb < threshold_mb * 2:
                status = "warning"
            else:
                status = "ok"

            return {
                "status": status,
                "available_mb": round(available_mb, 2),
                "total_mb": round(memory.total / (1024**2), 2),
                "used_percent": memory.percent,
            }

        except Exception as e:
            logger.warning("memory_health_check_failed", error=str(e))
            return {
                "status": "error",
                "error": str(e),
            }
