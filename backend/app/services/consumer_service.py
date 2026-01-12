"""
Consumer Service - Consumer lifecycle and session management.

BLACK BOX PRINCIPLE:
- Does NOT modify MediaSoup consumer creation logic
- Does NOT modify RTP capabilities negotiation
- ONLY manages consumer sessions, heartbeats, and cleanup

This service provides session management around existing consumer endpoints.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.consumer import Consumer, ConsumerState
from app.models.stream import Stream


class ConsumerService:
    """
    Service for managing consumer sessions.

    Features:
    - Heartbeat tracking
    - Automatic timeout and cleanup
    - Session statistics
    """

    def __init__(self):
        """Initialize the consumer service."""
        self.heartbeat_timeout_seconds = 60  # Consumers must heartbeat within 60 seconds
        self.cleanup_interval_seconds = 30  # Run cleanup every 30 seconds
        self.cleanup_task: Optional[asyncio.Task] = None
        logger.info("ConsumerService initialized")

    async def start_cleanup_task(self, db_session_factory):
        """
        Start background task for cleanup of stale consumers.

        Args:
            db_session_factory: Async context manager for database sessions
        """
        if self.cleanup_task is not None:
            logger.warning("Cleanup task already running")
            return

        async def cleanup_loop():
            """Background loop to clean up stale consumers."""
            while True:
                try:
                    await asyncio.sleep(self.cleanup_interval_seconds)

                    async with db_session_factory() as db:
                        await self.cleanup_stale_consumers(db)

                except asyncio.CancelledError:
                    logger.info("Cleanup task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in cleanup loop: {str(e)}")

        self.cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Started consumer cleanup task (interval: {self.cleanup_interval_seconds}s)")

    async def stop_cleanup_task(self):
        """Stop the background cleanup task."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
            logger.info("Stopped consumer cleanup task")

    async def record_heartbeat(
        self,
        consumer_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Record a heartbeat for a consumer.

        Consumers should call this periodically to indicate they're still active.

        Args:
            consumer_id: Consumer UUID
            db: Database session

        Returns:
            Dict with heartbeat acknowledgment

        Raises:
            ValueError: If consumer not found
        """
        # Get consumer
        consumer_query = select(Consumer).where(Consumer.id == consumer_id)
        consumer_result = await db.execute(consumer_query)
        consumer = consumer_result.scalar_one_or_none()

        if not consumer:
            raise ValueError(f"Consumer {consumer_id} not found")

        # Update last_seen_at
        consumer.last_seen_at = datetime.now(timezone.utc)
        await db.commit()

        logger.debug(f"Heartbeat recorded for consumer {consumer_id}")

        return {
            "consumer_id": str(consumer_id),
            "last_seen_at": consumer.last_seen_at.isoformat(),
            "status": "active"
        }

    async def cleanup_stale_consumers(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Clean up consumers that haven't sent heartbeat within timeout.

        Process:
        1. Find consumers with last_seen_at older than timeout
        2. Mark them as CLOSED
        3. Log cleanup action

        Args:
            db: Database session

        Returns:
            Dict with cleanup statistics
        """
        timeout_threshold = datetime.now(timezone.utc) - timedelta(
            seconds=self.heartbeat_timeout_seconds
        )

        # Find stale consumers (CONNECTED or CONNECTING state, but no recent heartbeat)
        stale_query = select(Consumer).where(
            and_(
                Consumer.state.in_([ConsumerState.CONNECTED, ConsumerState.CONNECTING]),
                Consumer.last_seen_at < timeout_threshold
            )
        )

        result = await db.execute(stale_query)
        stale_consumers = result.scalars().all()

        closed_count = 0

        for consumer in stale_consumers:
            # Calculate how long since last heartbeat
            time_since_heartbeat = datetime.now(timezone.utc) - consumer.last_seen_at
            minutes_stale = int(time_since_heartbeat.total_seconds() / 60)

            logger.warning(
                f"Closing stale consumer {consumer.id} (client: {consumer.client_id}, "
                f"stale for {minutes_stale} minutes)"
            )

            # Mark as CLOSED
            consumer.state = ConsumerState.CLOSED
            consumer.closed_at = datetime.now(timezone.utc)

            # Store cleanup reason in metadata
            if not consumer.extra_metadata:
                consumer.extra_metadata = {}

            consumer.extra_metadata["cleanup_reason"] = "heartbeat_timeout"
            consumer.extra_metadata["minutes_stale"] = minutes_stale

            closed_count += 1

        if closed_count > 0:
            await db.commit()
            logger.info(f"Cleaned up {closed_count} stale consumers")

        return {
            "cleaned_up": closed_count,
            "timeout_seconds": self.heartbeat_timeout_seconds,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }

    async def get_consumer_session_stats(
        self,
        consumer_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get session statistics for a consumer.

        Args:
            consumer_id: Consumer UUID
            db: Database session

        Returns:
            Dict with session stats

        Raises:
            ValueError: If consumer not found
        """
        # Get consumer
        consumer_query = select(Consumer).where(Consumer.id == consumer_id)
        consumer_result = await db.execute(consumer_query)
        consumer = consumer_result.scalar_one_or_none()

        if not consumer:
            raise ValueError(f"Consumer {consumer_id} not found")

        # Calculate session duration
        session_duration_seconds = None
        if consumer.created_at:
            end_time = consumer.closed_at if consumer.closed_at else datetime.now(timezone.utc)
            session_duration_seconds = (end_time - consumer.created_at).total_seconds()

        # Calculate time since last heartbeat
        seconds_since_heartbeat = None
        is_stale = False
        if consumer.last_seen_at:
            seconds_since_heartbeat = (
                datetime.now(timezone.utc) - consumer.last_seen_at
            ).total_seconds()
            is_stale = seconds_since_heartbeat > self.heartbeat_timeout_seconds

        return {
            "consumer_id": str(consumer_id),
            "client_id": consumer.client_id,
            "stream_id": str(consumer.stream_id),
            "state": consumer.state.value,
            "session_duration_seconds": int(session_duration_seconds) if session_duration_seconds else None,
            "created_at": consumer.created_at.isoformat() if consumer.created_at else None,
            "last_seen_at": consumer.last_seen_at.isoformat() if consumer.last_seen_at else None,
            "closed_at": consumer.closed_at.isoformat() if consumer.closed_at else None,
            "seconds_since_heartbeat": int(seconds_since_heartbeat) if seconds_since_heartbeat else None,
            "is_stale": is_stale,
            "mediasoup_consumer_id": consumer.mediasoup_consumer_id,
            "mediasoup_transport_id": consumer.mediasoup_transport_id,
            "metadata": consumer.extra_metadata
        }

    async def get_stream_consumer_stats(
        self,
        stream_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get consumer statistics for a stream.

        Args:
            stream_id: Stream UUID
            db: Database session

        Returns:
            Dict with stream consumer stats
        """
        # Get all consumers for stream
        consumers_query = select(Consumer).where(Consumer.stream_id == stream_id)
        result = await db.execute(consumers_query)
        consumers = result.scalars().all()

        # Count by state
        state_counts = {
            "connecting": 0,
            "connected": 0,
            "paused": 0,
            "closed": 0
        }

        active_consumers = []
        total_session_duration = 0

        for consumer in consumers:
            # Update state counts
            if consumer.state == ConsumerState.CONNECTING:
                state_counts["connecting"] += 1
            elif consumer.state == ConsumerState.CONNECTED:
                state_counts["connected"] += 1
                active_consumers.append({
                    "consumer_id": str(consumer.id),
                    "client_id": consumer.client_id,
                    "created_at": consumer.created_at.isoformat() if consumer.created_at else None
                })
            elif consumer.state == ConsumerState.PAUSED:
                state_counts["paused"] += 1
            elif consumer.state == ConsumerState.CLOSED:
                state_counts["closed"] += 1

            # Calculate total session duration
            if consumer.created_at:
                end_time = consumer.closed_at if consumer.closed_at else datetime.now(timezone.utc)
                session_duration = (end_time - consumer.created_at).total_seconds()
                total_session_duration += session_duration

        # Calculate average session duration
        avg_session_duration = None
        if len(consumers) > 0:
            avg_session_duration = total_session_duration / len(consumers)

        return {
            "stream_id": str(stream_id),
            "total_consumers": len(consumers),
            "active_consumers": state_counts["connecting"] + state_counts["connected"],
            "state_counts": state_counts,
            "active_consumer_list": active_consumers,
            "average_session_duration_seconds": int(avg_session_duration) if avg_session_duration else None,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }

    async def get_all_active_consumers(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get all active consumers across all streams.

        Args:
            db: Database session

        Returns:
            Dict with all active consumers
        """
        # Get active consumers (CONNECTING or CONNECTED)
        active_query = select(Consumer).where(
            Consumer.state.in_([ConsumerState.CONNECTING, ConsumerState.CONNECTED])
        )

        result = await db.execute(active_query)
        active_consumers = result.scalars().all()

        consumers_list = []

        for consumer in active_consumers:
            # Calculate time since last heartbeat
            seconds_since_heartbeat = None
            if consumer.last_seen_at:
                seconds_since_heartbeat = (
                    datetime.now(timezone.utc) - consumer.last_seen_at
                ).total_seconds()

            consumers_list.append({
                "consumer_id": str(consumer.id),
                "client_id": consumer.client_id,
                "stream_id": str(consumer.stream_id),
                "state": consumer.state.value,
                "created_at": consumer.created_at.isoformat() if consumer.created_at else None,
                "last_seen_at": consumer.last_seen_at.isoformat() if consumer.last_seen_at else None,
                "seconds_since_heartbeat": int(seconds_since_heartbeat) if seconds_since_heartbeat else None
            })

        return {
            "total_active": len(consumers_list),
            "consumers": consumers_list,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }

    async def force_close_consumer(
        self,
        consumer_id: UUID,
        reason: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Force close a consumer (admin operation).

        Args:
            consumer_id: Consumer UUID
            reason: Reason for force close
            db: Database session

        Returns:
            Dict with closure details

        Raises:
            ValueError: If consumer not found
        """
        # Get consumer
        consumer_query = select(Consumer).where(Consumer.id == consumer_id)
        consumer_result = await db.execute(consumer_query)
        consumer = consumer_result.scalar_one_or_none()

        if not consumer:
            raise ValueError(f"Consumer {consumer_id} not found")

        logger.warning(f"Force closing consumer {consumer_id}: {reason}")

        # Mark as CLOSED
        consumer.state = ConsumerState.CLOSED
        consumer.closed_at = datetime.now(timezone.utc)

        # Store reason in metadata
        if not consumer.extra_metadata:
            consumer.extra_metadata = {}

        consumer.extra_metadata["force_closed"] = True
        consumer.extra_metadata["close_reason"] = reason

        await db.commit()

        return {
            "consumer_id": str(consumer_id),
            "state": ConsumerState.CLOSED.value,
            "reason": reason,
            "closed_at": consumer.closed_at.isoformat()
        }


# Global service instance
consumer_service = ConsumerService()
