"""
Recording Management Service - Phase 3 VAS-MS-V2

BLACK BOX PRINCIPLE:
- Does NOT modify HLS recording logic
- ONLY provides management APIs around existing recordings

This service manages HLS recordings:
- Disk usage monitoring
- Retention policy enforcement
- Recording cleanup
- Recording metadata
"""
import os
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from uuid import UUID
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.stream import Stream


class RecordingManagementService:
    """
    Service for managing HLS recordings.

    Features:
    - Disk usage monitoring
    - Automatic cleanup based on retention policy
    - Recording metadata (segment count, total size, duration)
    """

    def __init__(self, recordings_base_path: str = "/recordings/hot"):
        """
        Initialize recording management service.

        Args:
            recordings_base_path: Base path where HLS recordings are stored
        """
        self.recordings_base_path = Path(recordings_base_path)
        self.default_retention_days = 7  # 7-day retention by default
        self.cleanup_task: Optional[asyncio.Task] = None
        logger.info(f"RecordingManagementService initialized (path: {recordings_base_path})")

    async def start_cleanup_task(self, db_session_factory):
        """
        Start background task for automatic recording cleanup.

        Args:
            db_session_factory: Async context manager for database sessions
        """
        if self.cleanup_task is not None:
            logger.warning("Recording cleanup task already running")
            return

        async def cleanup_loop():
            """Background loop to clean up old recordings."""
            while True:
                try:
                    # Run cleanup once per hour
                    await asyncio.sleep(3600)

                    async with db_session_factory() as db:
                        await self.cleanup_old_recordings(db)

                except asyncio.CancelledError:
                    logger.info("Recording cleanup task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in recording cleanup loop: {str(e)}")

        self.cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("Started recording cleanup task (runs hourly)")

    async def stop_cleanup_task(self):
        """Stop the background cleanup task."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
            logger.info("Stopped recording cleanup task")

    def get_stream_recording_path(self, stream_id: UUID) -> Path:
        """
        Get the recording directory path for a stream.

        Args:
            stream_id: Stream UUID

        Returns:
            Path to stream's recording directory
        """
        return self.recordings_base_path / str(stream_id)

    def get_recording_stats(self, stream_id: UUID) -> Dict[str, Any]:
        """
        Get statistics for a stream's recordings.

        Args:
            stream_id: Stream UUID

        Returns:
            Dict with recording statistics:
            - exists: Whether recording directory exists
            - segment_count: Number of .ts segments
            - total_size_bytes: Total size of all segments
            - total_size_mb: Total size in MB
            - oldest_segment_age_hours: Age of oldest segment in hours
            - disk_usage_percent: Disk usage percentage
        """
        recording_path = self.get_stream_recording_path(stream_id)

        if not recording_path.exists():
            return {
                "stream_id": str(stream_id),
                "exists": False,
                "message": "Recording directory does not exist"
            }

        try:
            # Count segments and calculate total size
            segment_files = list(recording_path.glob("*.ts"))
            segment_count = len(segment_files)

            total_size_bytes = 0
            oldest_segment_time = None

            for segment_file in segment_files:
                stat = segment_file.stat()
                total_size_bytes += stat.st_size

                # Track oldest segment
                mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                if oldest_segment_time is None or mtime < oldest_segment_time:
                    oldest_segment_time = mtime

            # Calculate oldest segment age
            oldest_segment_age_hours = None
            if oldest_segment_time:
                age_delta = datetime.now(timezone.utc) - oldest_segment_time
                oldest_segment_age_hours = age_delta.total_seconds() / 3600

            # Get disk usage
            disk_usage = os.statvfs(recording_path)
            disk_total = disk_usage.f_blocks * disk_usage.f_frsize
            disk_free = disk_usage.f_bfree * disk_usage.f_frsize
            disk_used = disk_total - disk_free
            disk_usage_percent = (disk_used / disk_total) * 100 if disk_total > 0 else 0

            return {
                "stream_id": str(stream_id),
                "exists": True,
                "recording_path": str(recording_path),
                "segment_count": segment_count,
                "total_size_bytes": total_size_bytes,
                "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
                "total_size_gb": round(total_size_bytes / (1024 * 1024 * 1024), 2),
                "oldest_segment_age_hours": round(oldest_segment_age_hours, 2) if oldest_segment_age_hours else None,
                "disk_usage_percent": round(disk_usage_percent, 2),
                "disk_total_gb": round(disk_total / (1024 * 1024 * 1024), 2),
                "disk_free_gb": round(disk_free / (1024 * 1024 * 1024), 2)
            }

        except Exception as e:
            logger.error(f"Error getting recording stats for stream {stream_id}: {str(e)}")
            return {
                "stream_id": str(stream_id),
                "exists": True,
                "error": str(e)
            }

    async def cleanup_stream_recordings(
        self,
        stream_id: UUID,
        retention_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Clean up old recordings for a stream.

        Removes segments older than retention period.

        Args:
            stream_id: Stream UUID
            retention_days: Retention period in days (default: 7)

        Returns:
            Dict with cleanup statistics
        """
        if retention_days is None:
            retention_days = self.default_retention_days

        recording_path = self.get_stream_recording_path(stream_id)

        if not recording_path.exists():
            return {
                "stream_id": str(stream_id),
                "deleted_count": 0,
                "deleted_size_bytes": 0,
                "message": "Recording directory does not exist"
            }

        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=retention_days)

            deleted_count = 0
            deleted_size_bytes = 0

            segment_files = list(recording_path.glob("*.ts"))

            for segment_file in segment_files:
                stat = segment_file.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

                # Delete if older than retention period
                if mtime < cutoff_time:
                    deleted_size_bytes += stat.st_size
                    segment_file.unlink()
                    deleted_count += 1

            logger.info(
                f"Cleaned up {deleted_count} segments for stream {stream_id} "
                f"({deleted_size_bytes / (1024 * 1024):.2f} MB freed)"
            )

            return {
                "stream_id": str(stream_id),
                "retention_days": retention_days,
                "deleted_count": deleted_count,
                "deleted_size_bytes": deleted_size_bytes,
                "deleted_size_mb": round(deleted_size_bytes / (1024 * 1024), 2),
                "cutoff_time": cutoff_time.isoformat()
            }

        except Exception as e:
            logger.error(f"Error cleaning up recordings for stream {stream_id}: {str(e)}")
            raise RuntimeError(f"Recording cleanup failed: {str(e)}")

    async def cleanup_old_recordings(
        self,
        db: AsyncSession,
        retention_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Clean up old recordings for all streams.

        Args:
            db: Database session
            retention_days: Retention period in days (default: 7)

        Returns:
            Dict with overall cleanup statistics
        """
        if retention_days is None:
            retention_days = self.default_retention_days

        logger.info(f"Running recording cleanup (retention: {retention_days} days)")

        # Get all streams
        streams_query = select(Stream)
        result = await db.execute(streams_query)
        streams = result.scalars().all()

        total_deleted_count = 0
        total_deleted_size_bytes = 0
        streams_cleaned = 0

        for stream in streams:
            try:
                cleanup_result = await self.cleanup_stream_recordings(
                    stream.id,
                    retention_days
                )

                deleted_count = cleanup_result.get("deleted_count", 0)
                if deleted_count > 0:
                    streams_cleaned += 1
                    total_deleted_count += deleted_count
                    total_deleted_size_bytes += cleanup_result.get("deleted_size_bytes", 0)

            except Exception as e:
                logger.error(f"Error cleaning stream {stream.id}: {str(e)}")

        logger.info(
            f"Recording cleanup complete: {total_deleted_count} segments deleted "
            f"from {streams_cleaned} streams "
            f"({total_deleted_size_bytes / (1024 * 1024):.2f} MB freed)"
        )

        return {
            "retention_days": retention_days,
            "streams_cleaned": streams_cleaned,
            "total_deleted_count": total_deleted_count,
            "total_deleted_size_bytes": total_deleted_size_bytes,
            "total_deleted_size_mb": round(total_deleted_size_bytes / (1024 * 1024), 2),
            "total_deleted_size_gb": round(total_deleted_size_bytes / (1024 * 1024 * 1024), 2)
        }

    def get_all_recordings_stats(self) -> Dict[str, Any]:
        """
        Get statistics for all recordings.

        Returns:
            Dict with overall recording statistics
        """
        if not self.recordings_base_path.exists():
            return {
                "exists": False,
                "message": "Recordings base path does not exist"
            }

        try:
            total_size_bytes = 0
            total_segments = 0
            stream_count = 0

            # Iterate through stream directories
            for stream_dir in self.recordings_base_path.iterdir():
                if stream_dir.is_dir():
                    stream_count += 1

                    # Count segments
                    segment_files = list(stream_dir.glob("*.ts"))
                    total_segments += len(segment_files)

                    # Calculate size
                    for segment_file in segment_files:
                        total_size_bytes += segment_file.stat().st_size

            # Get disk usage
            disk_usage = os.statvfs(self.recordings_base_path)
            disk_total = disk_usage.f_blocks * disk_usage.f_frsize
            disk_free = disk_usage.f_bfree * disk_usage.f_frsize
            disk_used = disk_total - disk_free
            disk_usage_percent = (disk_used / disk_total) * 100 if disk_total > 0 else 0

            return {
                "recordings_path": str(self.recordings_base_path),
                "stream_count": stream_count,
                "total_segments": total_segments,
                "total_size_bytes": total_size_bytes,
                "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
                "total_size_gb": round(total_size_bytes / (1024 * 1024 * 1024), 2),
                "disk_total_gb": round(disk_total / (1024 * 1024 * 1024), 2),
                "disk_used_gb": round(disk_used / (1024 * 1024 * 1024), 2),
                "disk_free_gb": round(disk_free / (1024 * 1024 * 1024), 2),
                "disk_usage_percent": round(disk_usage_percent, 2)
            }

        except Exception as e:
            logger.error(f"Error getting all recordings stats: {str(e)}")
            return {
                "error": str(e)
            }


# Global service instance
recording_management_service = RecordingManagementService()
