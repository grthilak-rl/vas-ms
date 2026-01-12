"""
Stream Ingestion Service - Wraps FFmpeg pipeline for RTSP to RTP/HLS conversion.

BLACK BOX PRINCIPLE:
- Does NOT modify FFmpeg commands (uses existing rtsp_pipeline logic)
- Does NOT modify codec configurations
- Does NOT modify SSRC capture logic
- ONLY wraps and orchestrates existing components

This service provides a clean API around the existing FFmpeg pipeline.
"""
import asyncio
import psutil
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.stream import Stream, StreamState
from app.models.producer import Producer, ProducerState
from app.models.device import Device
from app.services.stream_state_machine import transition, stream_state_machine
from app.services.rtsp_pipeline import (
    capture_ssrc_with_temp_ffmpeg,
    start_stream as rtsp_start_stream,
    stop_stream as rtsp_stop_stream,
    get_active_streams as rtsp_get_active_streams
)


class StreamIngestionService:
    """
    Service for managing stream ingestion from RTSP to RTP/HLS.

    Wraps existing FFmpeg-based pipeline without modifying it.
    Provides lifecycle management and health monitoring.
    """

    def __init__(self):
        """Initialize the stream ingestion service."""
        self.active_processes: Dict[str, Dict[str, Any]] = {}  # stream_id -> process info
        logger.info("StreamIngestionService initialized")

    async def start_ingestion(
        self,
        stream_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Start RTSP ingestion for a stream.

        Process:
        1. Get stream and camera details from database
        2. Transition stream to INITIALIZING
        3. Capture SSRC from RTSP stream (using existing logic)
        4. Start FFmpeg dual output: RTP + HLS (using existing logic)
        5. Create Producer record
        6. Transition stream to READY → LIVE

        Args:
            stream_id: Stream UUID
            db: Database session

        Returns:
            Dict with ingestion details (producer_id, ssrc, pid, etc.)

        Raises:
            ValueError: If stream not found or camera unavailable
            RuntimeError: If FFmpeg startup fails
        """
        stream_id_str = str(stream_id)

        # 1. Get stream from database
        stream_query = select(Stream).where(Stream.id == stream_id)
        stream_result = await db.execute(stream_query)
        stream = stream_result.scalar_one_or_none()

        if not stream:
            raise ValueError(f"Stream {stream_id} not found")

        # Get camera/device
        device_query = select(Device).where(Device.id == stream.camera_id)
        device_result = await db.execute(device_query)
        device = device_result.scalar_one_or_none()

        if not device:
            raise ValueError(f"Camera {stream.camera_id} not found")

        if not device.rtsp_url:
            raise ValueError(f"Camera {device.name} has no RTSP URL configured")

        logger.info(f"Starting ingestion for stream {stream_id} (camera: {device.name})")

        # 2. Transition to INITIALIZING
        await transition(
            stream=stream,
            to_state=StreamState.INITIALIZING,
            reason="Starting stream ingestion",
            metadata={"camera_name": device.name, "rtsp_url": device.rtsp_url},
            db=db
        )
        await db.commit()

        try:
            # 3. Capture SSRC (BLACK BOX - using existing function)
            logger.info(f"Capturing SSRC for stream {stream_id}")
            ssrc = await capture_ssrc_with_temp_ffmpeg(device.rtsp_url)

            if not ssrc:
                raise RuntimeError("Failed to capture SSRC from RTSP stream")

            logger.info(f"Captured SSRC: {ssrc} (0x{ssrc:08x})")

            # 4. Start FFmpeg dual output (BLACK BOX - using existing function)
            logger.info(f"Starting FFmpeg pipeline for stream {stream_id}")
            mediasoup_ip = "127.0.0.1"  # MediaSoup server IP
            mediasoup_video_port = 10000 + (ssrc % 50000)  # Dynamic port allocation

            ffmpeg_result = await rtsp_start_stream(
                stream_id=stream_id_str,
                rtsp_url=device.rtsp_url,
                mediasoup_ip=mediasoup_ip,
                mediasoup_video_port=mediasoup_video_port,
                ssrc=ssrc
            )

            logger.info(f"FFmpeg started: PID={ffmpeg_result.get('pid')}")

            # Store process info for health monitoring
            self.active_processes[stream_id_str] = {
                "pid": ffmpeg_result.get("pid"),
                "ssrc": ssrc,
                "rtp_port": mediasoup_video_port,
                "started_at": datetime.now(timezone.utc),
                "camera_id": stream.camera_id,
                "rtsp_url": device.rtsp_url
            }

            # 5. Transition to READY
            await transition(
                stream=stream,
                to_state=StreamState.READY,
                reason="FFmpeg started, SSRC captured",
                metadata={"ssrc": ssrc, "pid": ffmpeg_result.get("pid")},
                db=db
            )

            # Update stream codec config
            stream.codec_config = {
                "ssrc": ssrc,
                "rtp_port": mediasoup_video_port,
                "codec": "h264",
                "profile": "baseline"
            }
            stream.started_at = datetime.now(timezone.utc)

            await db.commit()

            logger.info(f"Stream {stream_id} transitioned to READY")

            return {
                "stream_id": stream_id_str,
                "ssrc": ssrc,
                "rtp_port": mediasoup_video_port,
                "pid": ffmpeg_result.get("pid"),
                "state": StreamState.READY.value,
                "camera_name": device.name
            }

        except Exception as e:
            logger.error(f"Failed to start ingestion for stream {stream_id}: {str(e)}")

            # Transition to ERROR state
            await transition(
                stream=stream,
                to_state=StreamState.ERROR,
                reason=f"Ingestion failed: {str(e)}",
                metadata={"error": str(e)},
                db=db
            )
            await db.commit()

            # Cleanup
            if stream_id_str in self.active_processes:
                del self.active_processes[stream_id_str]

            raise RuntimeError(f"Stream ingestion failed: {str(e)}")

    async def stop_ingestion(
        self,
        stream_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Stop RTSP ingestion for a stream.

        Process:
        1. Get stream from database
        2. Stop FFmpeg process (using existing logic)
        3. Transition stream to STOPPED
        4. Clean up tracking data

        Args:
            stream_id: Stream UUID
            db: Database session

        Returns:
            Dict with stop details
        """
        stream_id_str = str(stream_id)

        # Get stream
        stream_query = select(Stream).where(Stream.id == stream_id)
        stream_result = await db.execute(stream_query)
        stream = stream_result.scalar_one_or_none()

        if not stream:
            raise ValueError(f"Stream {stream_id} not found")

        logger.info(f"Stopping ingestion for stream {stream_id}")

        try:
            # Stop FFmpeg (BLACK BOX - using existing function)
            await rtsp_stop_stream(stream_id_str)

            # Transition to STOPPED
            await transition(
                stream=stream,
                to_state=StreamState.STOPPED,
                reason="Stream ingestion stopped",
                metadata={},
                db=db
            )

            stream.stopped_at = datetime.now(timezone.utc)
            await db.commit()

            # Clean up tracking
            if stream_id_str in self.active_processes:
                del self.active_processes[stream_id_str]

            logger.info(f"Stream {stream_id} stopped successfully")

            return {
                "stream_id": stream_id_str,
                "state": StreamState.STOPPED.value,
                "message": "Ingestion stopped successfully"
            }

        except Exception as e:
            logger.error(f"Error stopping stream {stream_id}: {str(e)}")
            raise RuntimeError(f"Failed to stop ingestion: {str(e)}")

    async def get_ingestion_health(
        self,
        stream_id: UUID
    ) -> Dict[str, Any]:
        """
        Get health status of stream ingestion.

        Checks:
        - FFmpeg process is alive
        - Process CPU/memory usage
        - Uptime

        Args:
            stream_id: Stream UUID

        Returns:
            Dict with health metrics
        """
        stream_id_str = str(stream_id)

        if stream_id_str not in self.active_processes:
            return {
                "stream_id": stream_id_str,
                "is_healthy": False,
                "status": "not_running",
                "message": "Stream ingestion not active"
            }

        process_info = self.active_processes[stream_id_str]
        pid = process_info.get("pid")

        if not pid:
            return {
                "stream_id": stream_id_str,
                "is_healthy": False,
                "status": "no_pid",
                "message": "No PID found for stream"
            }

        try:
            # Check if process exists
            process = psutil.Process(pid)

            if not process.is_running():
                return {
                    "stream_id": stream_id_str,
                    "is_healthy": False,
                    "status": "process_dead",
                    "message": f"FFmpeg process {pid} is not running"
                }

            # Get process metrics
            cpu_percent = process.cpu_percent(interval=0.1)
            memory_mb = process.memory_info().rss / (1024 * 1024)

            # Calculate uptime
            started_at = process_info.get("started_at")
            uptime_seconds = None
            if started_at:
                uptime_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()

            return {
                "stream_id": stream_id_str,
                "is_healthy": True,
                "status": "running",
                "pid": pid,
                "cpu_percent": round(cpu_percent, 2),
                "memory_mb": round(memory_mb, 2),
                "uptime_seconds": int(uptime_seconds) if uptime_seconds else None,
                "ssrc": process_info.get("ssrc"),
                "rtp_port": process_info.get("rtp_port")
            }

        except psutil.NoSuchProcess:
            return {
                "stream_id": stream_id_str,
                "is_healthy": False,
                "status": "process_not_found",
                "message": f"Process {pid} not found (may have crashed)"
            }
        except Exception as e:
            logger.error(f"Error checking health for stream {stream_id}: {str(e)}")
            return {
                "stream_id": stream_id_str,
                "is_healthy": False,
                "status": "error",
                "message": str(e)
            }

    async def get_all_active_ingestions(self) -> Dict[str, Any]:
        """
        Get status of all active stream ingestions.

        Returns:
            Dict with list of active streams and their health status
        """
        active_streams = []

        for stream_id, process_info in self.active_processes.items():
            health = await self.get_ingestion_health(UUID(stream_id))
            active_streams.append({
                "stream_id": stream_id,
                "health": health,
                "process_info": {
                    "ssrc": process_info.get("ssrc"),
                    "rtp_port": process_info.get("rtp_port"),
                    "started_at": process_info.get("started_at").isoformat() if process_info.get("started_at") else None
                }
            })

        return {
            "total_active": len(active_streams),
            "streams": active_streams
        }

    async def restart_ingestion(
        self,
        stream_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Restart stream ingestion (stop + start).

        Useful for recovering from errors or applying configuration changes.

        Args:
            stream_id: Stream UUID
            db: Database session

        Returns:
            Dict with restart details
        """
        logger.info(f"Restarting ingestion for stream {stream_id}")

        try:
            # Stop (ignore errors if already stopped)
            try:
                await self.stop_ingestion(stream_id, db)
            except Exception as e:
                logger.warning(f"Error during stop (continuing): {str(e)}")

            # Wait a bit for cleanup
            await asyncio.sleep(2)

            # Start
            result = await self.start_ingestion(stream_id, db)

            logger.info(f"Stream {stream_id} restarted successfully")

            return {
                "stream_id": str(stream_id),
                "status": "restarted",
                "ingestion": result
            }

        except Exception as e:
            logger.error(f"Failed to restart stream {stream_id}: {str(e)}")
            raise RuntimeError(f"Restart failed: {str(e)}")


# Global service instance
stream_ingestion_service = StreamIngestionService()
