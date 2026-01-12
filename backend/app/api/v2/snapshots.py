"""Snapshot endpoints for V2 API."""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Optional
from uuid import UUID
from datetime import datetime
from database import get_db, AsyncSessionLocal
from app.schemas.v2.snapshot import SnapshotCreate, SnapshotResponse, SnapshotListResponse
from app.models.snapshot import Snapshot
from app.models.stream import Stream, StreamState
from app.models.device import Device
from app.middleware.jwt_auth import get_current_user, require_scope
from loguru import logger
import os
import asyncio
import subprocess

router = APIRouter(prefix="/streams/{stream_id}/snapshots", tags=["Snapshots"])
snapshot_router = APIRouter(prefix="/snapshots", tags=["Snapshots"])

# Snapshot base directory
SNAPSHOT_BASE_DIR = "/app/snapshots"


async def capture_snapshot_image(
    snapshot_id: UUID,
    stream_id: UUID,
    camera_id: UUID,
    rtsp_url: str,
    source: str,
    timestamp: datetime
):
    """
    Background task to capture a single frame for a snapshot.

    For live snapshots: Captures current frame from RTSP stream
    For historical snapshots: Extracts frame from HLS recordings
    """
    logger.info(f"Starting image capture for snapshot {snapshot_id} ({source})")

    # Prepare output path
    stream_dir = os.path.join(SNAPSHOT_BASE_DIR, str(stream_id))
    os.makedirs(stream_dir, exist_ok=True)

    timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
    image_filename = f"{source}_{timestamp_str}.jpg"
    image_file_path = os.path.join(stream_dir, image_filename)

    try:
        if source == "live":
            # For live, capture single frame from RTSP stream
            logger.info(f"Capturing live snapshot from RTSP: {rtsp_url}")
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-rtsp_transport", "tcp",
                "-timeout", "5000000",
                "-i", rtsp_url,
                "-frames:v", "1",
                "-q:v", "2",
                image_file_path
            ]
        else:
            # For historical, extract from HLS recordings
            hls_base_dir = "/app/recordings/hot"
            device_recording_dir = os.path.join(hls_base_dir, str(camera_id))
            date_folder = timestamp.strftime("%Y%m%d")
            date_folder_path = os.path.join(device_recording_dir, date_folder)

            if not os.path.exists(date_folder_path):
                logger.error(f"Recording folder not found: {date_folder_path}")
                return

            # Find segment closest to timestamp
            target_ts = int(timestamp.timestamp())
            segment_files = []
            for f in sorted(os.listdir(date_folder_path)):
                if f.startswith('segment-') and f.endswith('.ts'):
                    try:
                        seg_ts = int(f.split('-')[1].split('.')[0])
                        segment_files.append((seg_ts, os.path.join(date_folder_path, f)))
                    except (ValueError, IndexError):
                        continue

            if not segment_files:
                logger.error(f"No segments found for timestamp {timestamp}")
                return

            # Find closest segment
            closest_segment = min(segment_files, key=lambda x: abs(x[0] - target_ts))
            segment_path = closest_segment[1]

            logger.info(f"Extracting frame from segment: {segment_path}")
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-i", segment_path,
                "-frames:v", "1",
                "-q:v", "2",
                image_file_path
            ]

        # Run FFmpeg
        logger.info(f"Running FFmpeg: {' '.join(ffmpeg_cmd[:8])}...")
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=15.0
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logger.error(f"FFmpeg timeout for snapshot {snapshot_id}")
            return

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"FFmpeg failed for snapshot {snapshot_id}: {error_msg[:500]}")
            return

        if not os.path.exists(image_file_path):
            logger.error(f"Image file not created for snapshot {snapshot_id}")
            return

        file_size = os.path.getsize(image_file_path)
        logger.info(f"Image captured for snapshot {snapshot_id}: {image_file_path} ({file_size} bytes)")

        # Get image dimensions using ffprobe
        width, height = None, None
        try:
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                image_file_path
            ]
            probe_process = await asyncio.create_subprocess_exec(
                *probe_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            probe_stdout, _ = await asyncio.wait_for(probe_process.communicate(), timeout=5.0)
            dimensions = probe_stdout.decode().strip().split(',')
            if len(dimensions) == 2:
                width, height = int(dimensions[0]), int(dimensions[1])
        except Exception as e:
            logger.warning(f"Could not get image dimensions: {e}")

        # Update database record with file path
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Snapshot).where(Snapshot.id == snapshot_id))
            snapshot = result.scalar_one_or_none()

            if snapshot:
                snapshot.file_path = image_file_path
                snapshot.file_size = file_size
                snapshot.width = width
                snapshot.height = height
                await db.commit()
                logger.info(f"Database updated for snapshot {snapshot_id}")

    except Exception as e:
        logger.error(f"Error capturing snapshot {snapshot_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


@snapshot_router.get("", response_model=SnapshotListResponse, dependencies=[Depends(require_scope("snapshots:read"))])
async def list_all_snapshots(
    stream_id: Optional[UUID] = Query(None, description="Filter by stream ID"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    source: Optional[str] = Query(None, description="Filter by source (live/historical)"),
    after: Optional[datetime] = Query(None, description="Filter snapshots after this timestamp"),
    before: Optional[datetime] = Query(None, description="Filter snapshots before this timestamp"),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SnapshotListResponse:
    """
    List all snapshots with optional filtering.

    Query parameters:
    - stream_id: Filter by specific stream
    - created_by: Filter by creator (e.g., "ruth-ai", "operator-john")
    - source: Filter by source type ("live" or "historical")
    - after: Only snapshots after this timestamp
    - before: Only snapshots before this timestamp
    - limit: Max results (1-100, default 100)
    - offset: Pagination offset
    """
    try:
        # Build query
        query = select(Snapshot)

        if stream_id:
            query = query.where(Snapshot.stream_id == stream_id)

        if created_by:
            query = query.where(Snapshot.created_by == created_by)

        if source:
            query = query.where(Snapshot.source == source)

        if after:
            query = query.where(Snapshot.timestamp >= after)

        if before:
            query = query.where(Snapshot.timestamp <= before)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar()

        # Apply pagination and execute
        query = query.order_by(Snapshot.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(query)
        snapshots = result.scalars().all()

        # Build response
        snapshot_responses = [
            SnapshotResponse(
                id=s.id,
                stream_id=s.stream_id,
                timestamp=s.timestamp,
                source=s.source,
                created_by=s.created_by,
                format=s.format,
                file_size=s.file_size,
                width=s.width,
                height=s.height,
                image_url=f"/v2/snapshots/{s.id}/image" if s.file_path else None,
                status="processing" if not s.file_path else "ready",
                metadata=s.extra_metadata,
                created_at=s.created_at
            )
            for s in snapshots
        ]

        logger.info(f"Listed {len(snapshot_responses)} snapshots (total: {total})")

        return SnapshotListResponse(
            snapshots=snapshot_responses,
            pagination={"total": total, "limit": limit, "offset": offset}
        )

    except Exception as e:
        logger.error(f"Error listing all snapshots: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_scope("snapshots:write"))])
async def create_snapshot(
    stream_id: UUID,
    request: SnapshotCreate,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SnapshotResponse:
    """
    Create a snapshot (single frame) for a stream.

    Source types:
    - 'live': Capture from current live stream (timestamp auto-set to now)
    - 'historical': Capture from HLS archive (timestamp required)
    """
    try:
        # Verify stream exists and get device info
        stream_query = select(Stream).where(Stream.id == stream_id)
        stream_result = await db.execute(stream_query)
        stream = stream_result.scalar_one_or_none()

        if not stream:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stream {stream_id} not found"
            )

        # Get device (camera) info for RTSP URL
        device_query = select(Device).where(Device.id == stream.camera_id)
        device_result = await db.execute(device_query)
        device = device_result.scalar_one_or_none()

        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Camera device not found for stream {stream_id}"
            )

        # Validate source-specific requirements
        timestamp = request.timestamp
        if request.source == "live":
            if stream.state != StreamState.LIVE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot create live snapshot: stream is in {stream.state.value} state"
                )
            timestamp = datetime.utcnow()
        elif request.source == "historical":
            if not timestamp:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="timestamp is required for historical snapshots"
                )

        # Create snapshot
        new_snapshot = Snapshot(
            stream_id=stream_id,
            timestamp=timestamp,
            source=request.source,
            created_by=request.created_by or current_user["client_id"],
            format="jpg",
            extra_metadata=request.metadata or {},
            file_path=""  # Will be set by background job
        )

        db.add(new_snapshot)
        await db.commit()
        await db.refresh(new_snapshot)

        logger.info(
            f"Created snapshot {new_snapshot.id} for stream {stream_id} "
            f"({request.source}) by {current_user['client_id']}"
        )

        # Trigger background job to capture frame
        background_tasks.add_task(
            capture_snapshot_image,
            snapshot_id=new_snapshot.id,
            stream_id=stream_id,
            camera_id=stream.camera_id,
            rtsp_url=device.rtsp_url,
            source=request.source,
            timestamp=timestamp
        )

        return SnapshotResponse(
            id=new_snapshot.id,
            stream_id=new_snapshot.stream_id,
            timestamp=new_snapshot.timestamp,
            source=new_snapshot.source,
            created_by=new_snapshot.created_by,
            format=new_snapshot.format,
            file_size=new_snapshot.file_size,
            width=new_snapshot.width,
            height=new_snapshot.height,
            image_url=f"/v2/snapshots/{new_snapshot.id}/image" if new_snapshot.file_path else None,
            status="processing",  # Will become "ready" after background task completes
            metadata=new_snapshot.extra_metadata,
            created_at=new_snapshot.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating snapshot: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("", response_model=SnapshotListResponse, dependencies=[Depends(require_scope("snapshots:read"))])
async def list_snapshots(
    stream_id: UUID,
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    after: Optional[datetime] = Query(None, description="Filter snapshots after this timestamp"),
    before: Optional[datetime] = Query(None, description="Filter snapshots before this timestamp"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SnapshotListResponse:
    """
    List snapshots for a specific stream with optional filtering.

    Query parameters:
    - created_by: Filter by creator (e.g., "ruth-ai", "operator-john")
    - after: Only snapshots after this timestamp
    - before: Only snapshots before this timestamp
    - limit: Max results (1-100, default 50)
    - offset: Pagination offset
    """
    try:
        # Build query
        query = select(Snapshot).where(Snapshot.stream_id == stream_id)

        if created_by:
            query = query.where(Snapshot.created_by == created_by)

        if after:
            query = query.where(Snapshot.timestamp >= after)

        if before:
            query = query.where(Snapshot.timestamp <= before)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar()

        # Apply pagination and execute
        query = query.order_by(Snapshot.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(query)
        snapshots = result.scalars().all()

        # Build response
        snapshot_responses = [
            SnapshotResponse(
                id=s.id,
                stream_id=s.stream_id,
                timestamp=s.timestamp,
                source=s.source,
                created_by=s.created_by,
                format=s.format,
                file_size=s.file_size,
                width=s.width,
                height=s.height,
                image_url=f"/v2/snapshots/{s.id}/image" if s.file_path else None,
                status="processing" if not s.file_path else "ready",
                metadata=s.extra_metadata,
                created_at=s.created_at
            )
            for s in snapshots
        ]

        logger.info(f"Listed {len(snapshot_responses)} snapshots for stream {stream_id}")

        return SnapshotListResponse(
            snapshots=snapshot_responses,
            pagination={"total": total, "limit": limit, "offset": offset}
        )

    except Exception as e:
        logger.error(f"Error listing snapshots: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@snapshot_router.get("/{snapshot_id}", response_model=SnapshotResponse, dependencies=[Depends(require_scope("snapshots:read"))])
async def get_snapshot(
    snapshot_id: UUID,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> SnapshotResponse:
    """
    Get detailed information about a specific snapshot.
    """
    try:
        query = select(Snapshot).where(Snapshot.id == snapshot_id)
        result = await db.execute(query)
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapshot {snapshot_id} not found"
            )

        logger.info(f"Retrieved snapshot {snapshot_id}")

        return SnapshotResponse(
            id=snapshot.id,
            stream_id=snapshot.stream_id,
            timestamp=snapshot.timestamp,
            source=snapshot.source,
            created_by=snapshot.created_by,
            format=snapshot.format,
            file_size=snapshot.file_size,
            width=snapshot.width,
            height=snapshot.height,
            image_url=f"/v2/snapshots/{snapshot.id}/image" if snapshot.file_path else None,
            status="processing" if not snapshot.file_path else "ready",
            metadata=snapshot.extra_metadata,
            created_at=snapshot.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving snapshot: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@snapshot_router.get("/{snapshot_id}/image", dependencies=[Depends(require_scope("snapshots:read"))])
async def get_snapshot_image(
    snapshot_id: UUID,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download the image file for a snapshot.

    Returns the image file (typically JPG) for download or display.
    """
    try:
        query = select(Snapshot).where(Snapshot.id == snapshot_id)
        result = await db.execute(query)
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapshot {snapshot_id} not found"
            )

        if not snapshot.file_path or not os.path.exists(snapshot.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image file not found or still processing"
            )

        logger.info(f"Serving image for snapshot {snapshot_id}")

        return FileResponse(
            path=snapshot.file_path,
            media_type=f"image/{snapshot.format}",
            filename=f"snapshot_{snapshot_id}.{snapshot.format}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving snapshot image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@snapshot_router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_scope("snapshots:write"))])
async def delete_snapshot(
    snapshot_id: UUID,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a snapshot and its associated image file.
    """
    try:
        query = select(Snapshot).where(Snapshot.id == snapshot_id)
        result = await db.execute(query)
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapshot {snapshot_id} not found"
            )

        # Delete physical file
        if snapshot.file_path and os.path.exists(snapshot.file_path):
            try:
                os.remove(snapshot.file_path)
            except Exception as e:
                logger.warning(f"Failed to delete image file: {str(e)}")

        # Delete database record
        await db.delete(snapshot)
        await db.commit()

        logger.info(f"Deleted snapshot {snapshot_id} by {current_user['client_id']}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting snapshot: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
