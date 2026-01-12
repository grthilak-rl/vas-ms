"""Bookmark endpoints for V2 API."""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Optional
from uuid import UUID
from datetime import datetime, timedelta
from database import get_db, AsyncSessionLocal
from app.schemas.v2.bookmark import BookmarkCreate, BookmarkResponse, BookmarkListResponse, BookmarkUpdate
from app.models.bookmark import Bookmark
from app.models.stream import Stream, StreamState
from app.models.device import Device
from app.middleware.jwt_auth import get_current_user, require_scope
from loguru import logger
import os
import asyncio
import subprocess

router = APIRouter(prefix="/streams/{stream_id}/bookmarks", tags=["Bookmarks"])
bookmark_router = APIRouter(prefix="/bookmarks", tags=["Bookmarks"])

# Bookmark base directory
BOOKMARK_BASE_DIR = "/bookmarks"


async def extract_bookmark_video(
    bookmark_id: UUID,
    stream_id: UUID,
    camera_id: UUID,
    rtsp_url: str,
    source: str,
    center_timestamp: datetime,
    start_timestamp: datetime,
    end_timestamp: datetime,
    duration_seconds: int
):
    """
    Background task to extract video clip for a bookmark.

    For live bookmarks: Captures 6 seconds from RTSP stream
    For historical bookmarks: Extracts from HLS recordings
    """
    logger.info(f"Starting video extraction for bookmark {bookmark_id} ({source})")

    # Prepare output paths
    stream_dir = os.path.join(BOOKMARK_BASE_DIR, str(stream_id))
    os.makedirs(stream_dir, exist_ok=True)

    timestamp_str = center_timestamp.strftime('%Y%m%d_%H%M%S')
    video_filename = f"{source}_{timestamp_str}.mp4"
    video_file_path = os.path.join(stream_dir, video_filename)
    thumbnail_filename = f"{source}_{timestamp_str}_thumb.jpg"
    thumbnail_path = os.path.join(stream_dir, thumbnail_filename)

    try:
        if source == "live":
            # For live, capture directly from RTSP stream
            logger.info(f"Capturing live bookmark from RTSP: {rtsp_url}")
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-rtsp_transport", "tcp",
                "-timeout", "5000000",
                "-i", rtsp_url,
                "-t", str(duration_seconds),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-an",  # No audio to speed up
                "-movflags", "+faststart",
                video_file_path
            ]
        else:
            # For historical, extract from HLS recordings
            hls_base_dir = "/app/recordings/hot"
            device_recording_dir = os.path.join(hls_base_dir, str(camera_id))
            date_folder = start_timestamp.strftime("%Y%m%d")
            date_folder_path = os.path.join(device_recording_dir, date_folder)

            if not os.path.exists(date_folder_path):
                logger.error(f"Recording folder not found: {date_folder_path}")
                return

            # Find segments covering the time range
            center_unix_ts = int(center_timestamp.timestamp())
            start_unix_ts = int(start_timestamp.timestamp())
            end_unix_ts = int(end_timestamp.timestamp())

            # List all segment files and find matching ones
            segment_files = []
            for f in sorted(os.listdir(date_folder_path)):
                if f.startswith('segment-') and f.endswith('.ts'):
                    try:
                        seg_ts = int(f.split('-')[1].split('.')[0])
                        # Assume 2-second segments, include if overlaps with range
                        seg_end_ts = seg_ts + 2
                        if (start_unix_ts <= seg_end_ts and end_unix_ts >= seg_ts):
                            segment_files.append((seg_ts, os.path.join(date_folder_path, f)))
                    except (ValueError, IndexError):
                        continue

            if not segment_files:
                logger.error(f"No segments found for time range {start_timestamp} to {end_timestamp}")
                return

            segment_files.sort(key=lambda x: x[0])
            logger.info(f"Found {len(segment_files)} segments for historical bookmark")

            # Create concat file
            concat_file_path = os.path.join(stream_dir, f"concat_{bookmark_id}.txt")
            with open(concat_file_path, 'w') as f:
                for seg_ts, seg_path in segment_files:
                    f.write(f"file '{seg_path}'\n")

            # Calculate seek offset
            first_segment_ts = segment_files[0][0]
            seek_offset = max(0, start_unix_ts - first_segment_ts)

            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file_path,
                "-ss", str(seek_offset),
                "-t", str(duration_seconds),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-an",
                "-movflags", "+faststart",
                video_file_path
            ]

        # Run FFmpeg
        logger.info(f"Running FFmpeg: {' '.join(ffmpeg_cmd[:10])}...")
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logger.error(f"FFmpeg timeout for bookmark {bookmark_id}")
            return

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"FFmpeg failed for bookmark {bookmark_id}: {error_msg[:500]}")
            return

        if not os.path.exists(video_file_path):
            logger.error(f"Video file not created for bookmark {bookmark_id}")
            return

        file_size = os.path.getsize(video_file_path)
        logger.info(f"✅ Video extracted for bookmark {bookmark_id}: {video_file_path} ({file_size} bytes)")

        # Generate thumbnail
        thumb_cmd = [
            "ffmpeg",
            "-y",
            "-ss", "00:00:03",
            "-i", video_file_path,
            "-frames:v", "1",
            "-q:v", "2",
            thumbnail_path
        ]

        thumb_process = await asyncio.create_subprocess_exec(
            *thumb_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        await asyncio.wait_for(thumb_process.communicate(), timeout=10.0)

        if os.path.exists(thumbnail_path):
            logger.info(f"✅ Thumbnail generated for bookmark {bookmark_id}")

        # Update database record with file paths
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Bookmark).where(Bookmark.id == bookmark_id))
            bookmark = result.scalar_one_or_none()

            if bookmark:
                bookmark.video_file_path = video_file_path
                bookmark.thumbnail_path = thumbnail_path if os.path.exists(thumbnail_path) else None
                bookmark.file_size = file_size
                await db.commit()
                logger.info(f"✅ Database updated for bookmark {bookmark_id}")

        # Cleanup concat file if historical
        if source == "historical":
            concat_file = os.path.join(stream_dir, f"concat_{bookmark_id}.txt")
            if os.path.exists(concat_file):
                os.remove(concat_file)

    except Exception as e:
        logger.error(f"Error extracting video for bookmark {bookmark_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


@bookmark_router.get("", response_model=BookmarkListResponse, dependencies=[Depends(require_scope("bookmarks:read"))])
async def list_all_bookmarks(
    stream_id: Optional[UUID] = Query(None, description="Filter by stream ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    source: Optional[str] = Query(None, description="Filter by source (live/historical)"),
    start_after: Optional[datetime] = Query(None, description="Filter bookmarks after this time"),
    start_before: Optional[datetime] = Query(None, description="Filter bookmarks before this time"),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BookmarkListResponse:
    """
    List all bookmarks with optional filtering.

    Query parameters:
    - stream_id: Filter by specific stream
    - event_type: Filter by event type (e.g., "person_detected", "anomaly")
    - created_by: Filter by creator (e.g., "ruth-ai", "operator-john")
    - source: Filter by source type ("live" or "historical")
    - start_after: Only bookmarks starting after this timestamp
    - start_before: Only bookmarks starting before this timestamp
    - limit: Max results (1-100, default 100)
    - offset: Pagination offset
    """
    try:
        # Build query
        query = select(Bookmark)

        if stream_id:
            query = query.where(Bookmark.stream_id == stream_id)

        if event_type:
            query = query.where(Bookmark.event_type == event_type)

        if created_by:
            query = query.where(Bookmark.created_by == created_by)

        if source:
            query = query.where(Bookmark.source == source)

        if start_after:
            query = query.where(Bookmark.start_timestamp >= start_after)

        if start_before:
            query = query.where(Bookmark.start_timestamp <= start_before)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar()

        # Apply pagination and execute
        query = query.order_by(Bookmark.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(query)
        bookmarks = result.scalars().all()

        # Build response (using correct model field names)
        bookmark_responses = [
            BookmarkResponse(
                id=b.id,
                stream_id=b.stream_id,
                center_timestamp=b.center_timestamp,
                start_time=b.start_timestamp,  # Model uses start_timestamp
                end_time=b.end_timestamp,      # Model uses end_timestamp
                duration_seconds=float(b.duration),  # Model uses duration (Integer)
                source=b.source,
                label=b.label,
                created_by=b.created_by,
                event_type=b.event_type,
                confidence=b.confidence,
                tags=b.tags or [],
                video_url=f"/v2/bookmarks/{b.id}/video" if b.video_file_path else None,
                thumbnail_url=f"/v2/bookmarks/{b.id}/thumbnail" if b.thumbnail_path else None,
                status="processing" if not b.video_file_path else "ready",
                metadata=b.extra_metadata or {},
                created_at=b.created_at
            )
            for b in bookmarks
        ]

        logger.info(f"Listed {len(bookmark_responses)} bookmarks (total: {total})")

        return BookmarkListResponse(
            bookmarks=bookmark_responses,
            pagination={"total": total, "limit": limit, "offset": offset}
        )

    except Exception as e:
        logger.error(f"Error listing all bookmarks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("", response_model=BookmarkResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_scope("bookmarks:write"))])
async def create_bookmark(
    stream_id: UUID,
    request: BookmarkCreate,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BookmarkResponse:
    """
    Create a bookmark (video clip) for a stream.

    Source types:
    - 'live': Capture from current live stream (center_timestamp auto-set to now)
    - 'historical': Capture from HLS archive (center_timestamp required)

    The bookmark will span [center_timestamp - before_seconds, center_timestamp + after_seconds].
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
        center_timestamp = request.center_timestamp
        if request.source == "live":
            if stream.state != StreamState.LIVE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot create live bookmark: stream is in {stream.state.value} state"
                )
            center_timestamp = datetime.utcnow()
        elif request.source == "historical":
            if not center_timestamp:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="center_timestamp is required for historical bookmarks"
                )

        # Calculate time range
        before_seconds = request.before_seconds or 5
        after_seconds = request.after_seconds or 5
        start_time = center_timestamp - timedelta(seconds=before_seconds)
        end_time = center_timestamp + timedelta(seconds=after_seconds)
        duration_seconds = (end_time - start_time).total_seconds()

        # Create bookmark (matching Bookmark model field names)
        new_bookmark = Bookmark(
            stream_id=stream_id,
            center_timestamp=center_timestamp,
            start_timestamp=start_time,  # Model uses start_timestamp
            end_timestamp=end_time,      # Model uses end_timestamp
            duration=int(duration_seconds),  # Model uses duration (Integer)
            source=request.source,
            label=request.label,
            created_by=request.created_by or current_user["client_id"],
            event_type=request.event_type,
            confidence=request.confidence,
            tags=request.tags or [],
            extra_metadata=request.metadata or {},
            video_file_path=""  # Will be populated by background job
        )

        db.add(new_bookmark)
        await db.commit()
        await db.refresh(new_bookmark)

        logger.info(
            f"Created bookmark {new_bookmark.id} for stream {stream_id} "
            f"({request.source}) by {current_user['client_id']}"
        )

        # Trigger background job to extract video clip
        background_tasks.add_task(
            extract_bookmark_video,
            bookmark_id=new_bookmark.id,
            stream_id=stream_id,
            camera_id=stream.camera_id,
            rtsp_url=device.rtsp_url,
            source=request.source,
            center_timestamp=center_timestamp,
            start_timestamp=start_time,
            end_timestamp=end_time,
            duration_seconds=int(duration_seconds)
        )

        return BookmarkResponse(
            id=new_bookmark.id,
            stream_id=new_bookmark.stream_id,
            center_timestamp=new_bookmark.center_timestamp,
            start_time=new_bookmark.start_timestamp,  # Model uses start_timestamp
            end_time=new_bookmark.end_timestamp,      # Model uses end_timestamp
            duration_seconds=float(new_bookmark.duration),  # Model uses duration (Integer)
            source=new_bookmark.source,
            label=new_bookmark.label,
            created_by=new_bookmark.created_by,
            event_type=new_bookmark.event_type,
            confidence=new_bookmark.confidence,
            tags=new_bookmark.tags or [],
            video_url=f"/v2/bookmarks/{new_bookmark.id}/video" if new_bookmark.video_file_path else None,
            thumbnail_url=f"/v2/bookmarks/{new_bookmark.id}/thumbnail" if new_bookmark.thumbnail_path else None,
            status="processing" if not new_bookmark.video_file_path else "ready",
            metadata=new_bookmark.extra_metadata or {},
            created_at=new_bookmark.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating bookmark: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("", response_model=BookmarkListResponse, dependencies=[Depends(require_scope("bookmarks:read"))])
async def list_bookmarks(
    stream_id: UUID,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    start_after: Optional[datetime] = Query(None, description="Filter bookmarks after this time"),
    start_before: Optional[datetime] = Query(None, description="Filter bookmarks before this time"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BookmarkListResponse:
    """
    List bookmarks for a specific stream with optional filtering.

    Query parameters:
    - event_type: Filter by event type (e.g., "person_detected", "anomaly")
    - created_by: Filter by creator (e.g., "ruth-ai", "operator-john")
    - start_after: Only bookmarks starting after this timestamp
    - start_before: Only bookmarks starting before this timestamp
    - limit: Max results (1-100, default 50)
    - offset: Pagination offset
    """
    try:
        # Build query
        query = select(Bookmark).where(Bookmark.stream_id == stream_id)

        if event_type:
            query = query.where(Bookmark.event_type == event_type)

        if created_by:
            query = query.where(Bookmark.created_by == created_by)

        if start_after:
            query = query.where(Bookmark.start_timestamp >= start_after)

        if start_before:
            query = query.where(Bookmark.start_timestamp <= start_before)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar()

        # Apply pagination and execute
        query = query.order_by(Bookmark.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(query)
        bookmarks = result.scalars().all()

        # Build response (using correct model field names)
        bookmark_responses = [
            BookmarkResponse(
                id=b.id,
                stream_id=b.stream_id,
                center_timestamp=b.center_timestamp,
                start_time=b.start_timestamp,
                end_time=b.end_timestamp,
                duration_seconds=float(b.duration),
                source=b.source,
                label=b.label,
                created_by=b.created_by,
                event_type=b.event_type,
                confidence=b.confidence,
                tags=b.tags or [],
                video_url=f"/v2/bookmarks/{b.id}/video" if b.video_file_path else None,
                thumbnail_url=f"/v2/bookmarks/{b.id}/thumbnail" if b.thumbnail_path else None,
                status="processing" if not b.video_file_path else "ready",
                metadata=b.extra_metadata or {},
                created_at=b.created_at
            )
            for b in bookmarks
        ]

        logger.info(f"Listed {len(bookmark_responses)} bookmarks for stream {stream_id}")

        return BookmarkListResponse(
            bookmarks=bookmark_responses,
            pagination={"total": total, "limit": limit, "offset": offset}
        )

    except Exception as e:
        logger.error(f"Error listing bookmarks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@bookmark_router.get("/{bookmark_id}", response_model=BookmarkResponse, dependencies=[Depends(require_scope("bookmarks:read"))])
async def get_bookmark(
    bookmark_id: UUID,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BookmarkResponse:
    """
    Get detailed information about a specific bookmark.
    """
    try:
        query = select(Bookmark).where(Bookmark.id == bookmark_id)
        result = await db.execute(query)
        bookmark = result.scalar_one_or_none()

        if not bookmark:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bookmark {bookmark_id} not found"
            )

        logger.info(f"Retrieved bookmark {bookmark_id}")

        return BookmarkResponse(
            id=bookmark.id,
            stream_id=bookmark.stream_id,
            center_timestamp=bookmark.center_timestamp,
            start_time=bookmark.start_timestamp,
            end_time=bookmark.end_timestamp,
            duration_seconds=float(bookmark.duration),
            source=bookmark.source,
            label=bookmark.label,
            created_by=bookmark.created_by,
            event_type=bookmark.event_type,
            confidence=bookmark.confidence,
            tags=bookmark.tags or [],
            video_url=f"/v2/bookmarks/{bookmark.id}/video" if bookmark.video_file_path else None,
            thumbnail_url=f"/v2/bookmarks/{bookmark.id}/thumbnail" if bookmark.thumbnail_path else None,
            status="processing" if not bookmark.video_file_path else "ready",
            metadata=bookmark.extra_metadata or {},
            created_at=bookmark.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving bookmark: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@bookmark_router.get("/{bookmark_id}/video", dependencies=[Depends(require_scope("bookmarks:read"))])
async def get_bookmark_video(
    bookmark_id: UUID,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download the video clip for a bookmark.

    Returns the video file (typically MP4) for download or streaming.
    """
    try:
        query = select(Bookmark).where(Bookmark.id == bookmark_id)
        result = await db.execute(query)
        bookmark = result.scalar_one_or_none()

        if not bookmark:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bookmark {bookmark_id} not found"
            )

        if not bookmark.video_file_path or not os.path.exists(bookmark.video_file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not found or still processing"
            )

        logger.info(f"Serving video for bookmark {bookmark_id}")

        return FileResponse(
            path=bookmark.video_file_path,
            media_type="video/mp4",
            filename=f"bookmark_{bookmark_id}.mp4"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving bookmark video: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@bookmark_router.get("/{bookmark_id}/thumbnail", dependencies=[Depends(require_scope("bookmarks:read"))])
async def get_bookmark_thumbnail(
    bookmark_id: UUID,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the thumbnail image for a bookmark.

    Returns the thumbnail (typically JPG) for preview purposes.
    """
    try:
        query = select(Bookmark).where(Bookmark.id == bookmark_id)
        result = await db.execute(query)
        bookmark = result.scalar_one_or_none()

        if not bookmark:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bookmark {bookmark_id} not found"
            )

        if not bookmark.thumbnail_path or not os.path.exists(bookmark.thumbnail_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thumbnail not found or still processing"
            )

        logger.info(f"Serving thumbnail for bookmark {bookmark_id}")

        return FileResponse(
            path=bookmark.thumbnail_path,
            media_type="image/jpeg",
            filename=f"bookmark_{bookmark_id}_thumb.jpg"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving bookmark thumbnail: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@bookmark_router.put("/{bookmark_id}", response_model=BookmarkResponse, dependencies=[Depends(require_scope("bookmarks:write"))])
async def update_bookmark(
    bookmark_id: UUID,
    request: BookmarkUpdate,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BookmarkResponse:
    """
    Update bookmark metadata (label, tags, event_type, etc.).

    Cannot modify timestamps or video content, only metadata fields.
    """
    try:
        query = select(Bookmark).where(Bookmark.id == bookmark_id)
        result = await db.execute(query)
        bookmark = result.scalar_one_or_none()

        if not bookmark:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bookmark {bookmark_id} not found"
            )

        # Update fields if provided
        if request.label is not None:
            bookmark.label = request.label

        if request.event_type is not None:
            bookmark.event_type = request.event_type

        if request.confidence is not None:
            bookmark.confidence = request.confidence

        if request.tags is not None:
            bookmark.tags = request.tags

        if request.metadata is not None:
            bookmark.extra_metadata = request.metadata

        await db.commit()
        await db.refresh(bookmark)

        logger.info(f"Updated bookmark {bookmark_id} by {current_user['client_id']}")

        return BookmarkResponse(
            id=bookmark.id,
            stream_id=bookmark.stream_id,
            center_timestamp=bookmark.center_timestamp,
            start_time=bookmark.start_timestamp,
            end_time=bookmark.end_timestamp,
            duration_seconds=float(bookmark.duration),
            source=bookmark.source,
            label=bookmark.label,
            created_by=bookmark.created_by,
            event_type=bookmark.event_type,
            confidence=bookmark.confidence,
            tags=bookmark.tags or [],
            video_url=f"/v2/bookmarks/{bookmark.id}/video" if bookmark.video_file_path else None,
            thumbnail_url=f"/v2/bookmarks/{bookmark.id}/thumbnail" if bookmark.thumbnail_path else None,
            status="processing" if not bookmark.video_file_path else "ready",
            metadata=bookmark.extra_metadata or {},
            created_at=bookmark.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating bookmark: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@bookmark_router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_scope("bookmarks:write"))])
async def delete_bookmark(
    bookmark_id: UUID,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a bookmark and its associated files.
    """
    try:
        query = select(Bookmark).where(Bookmark.id == bookmark_id)
        result = await db.execute(query)
        bookmark = result.scalar_one_or_none()

        if not bookmark:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bookmark {bookmark_id} not found"
            )

        # Delete physical files
        if bookmark.video_file_path and os.path.exists(bookmark.video_file_path):
            try:
                os.remove(bookmark.video_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete video file: {str(e)}")

        if bookmark.thumbnail_path and os.path.exists(bookmark.thumbnail_path):
            try:
                os.remove(bookmark.thumbnail_path)
            except Exception as e:
                logger.warning(f"Failed to delete thumbnail: {str(e)}")

        # Delete database record
        await db.delete(bookmark)
        await db.commit()

        logger.info(f"Deleted bookmark {bookmark_id} by {current_user['client_id']}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting bookmark: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
