"""
Producer Service - Wraps MediaSoupClient for producer lifecycle management.

BLACK BOX PRINCIPLE:
- Does NOT modify MediaSoup codec configurations
- Does NOT modify RTP parameters
- ONLY wraps MediaSoupClient and manages producer database records

This service provides a clean API around the existing MediaSoup integration.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.stream import Stream, StreamState
from app.models.producer import Producer, ProducerState
from app.services.mediasoup_client import MediaSoupClient
from app.services.stream_state_machine import transition
import os


class ProducerService:
    """
    Service for managing MediaSoup producers.

    Wraps MediaSoupClient without modifying its behavior.
    Provides lifecycle management and database persistence.
    """

    def __init__(self):
        """Initialize the producer service."""
        mediasoup_url = os.getenv("MEDIASOUP_URL", "ws://localhost:3001")
        self.mediasoup_client = MediaSoupClient(mediasoup_url)
        self.active_producers: Dict[str, Dict[str, Any]] = {}  # producer_id -> info
        logger.info(f"ProducerService initialized (MediaSoup: {mediasoup_url})")

    async def create_producer(
        self,
        stream_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Create a MediaSoup producer for a stream.

        Process:
        1. Get stream from database (must be in READY state)
        2. Create MediaSoup router and RTP transport (BLACK BOX)
        3. Create MediaSoup producer with SSRC (BLACK BOX)
        4. Save Producer record to database
        5. Transition stream to LIVE

        Args:
            stream_id: Stream UUID
            db: Database session

        Returns:
            Dict with producer details

        Raises:
            ValueError: If stream not found or not in READY state
            RuntimeError: If MediaSoup producer creation fails
        """
        # 1. Get stream
        stream_query = select(Stream).where(Stream.id == stream_id)
        stream_result = await db.execute(stream_query)
        stream = stream_result.scalar_one_or_none()

        if not stream:
            raise ValueError(f"Stream {stream_id} not found")

        if stream.state != StreamState.READY:
            raise ValueError(
                f"Stream must be in READY state to create producer (current: {stream.state.value})"
            )

        # Get codec config (contains SSRC)
        ssrc = stream.codec_config.get("ssrc")
        rtp_port = stream.codec_config.get("rtp_port")

        if not ssrc or not rtp_port:
            raise ValueError("Stream codec_config missing SSRC or RTP port")

        logger.info(f"Creating MediaSoup producer for stream {stream_id} (SSRC: {ssrc})")

        try:
            # 2. Connect to MediaSoup
            await self.mediasoup_client.connect()

            # Create router (BLACK BOX)
            room_id = str(stream_id)
            router_response = await self.mediasoup_client.create_router(room_id)
            router_id = router_response.get("id")

            if not router_id:
                raise RuntimeError("Failed to create MediaSoup router")

            logger.info(f"Created MediaSoup router: {router_id}")

            # Create RTP transport (BLACK BOX)
            transport_response = await self.mediasoup_client.create_rtp_transport(
                router_id=router_id,
                port=rtp_port
            )
            transport_id = transport_response.get("id")

            if not transport_id:
                raise RuntimeError("Failed to create RTP transport")

            logger.info(f"Created RTP transport: {transport_id} on port {rtp_port}")

            # 3. Create producer (BLACK BOX)
            producer_response = await self.mediasoup_client.create_producer(
                transport_id=transport_id,
                kind="video",
                rtp_parameters={
                    "codecs": [{
                        "mimeType": "video/H264",
                        "payloadType": 96,
                        "clockRate": 90000,
                        "parameters": {
                            "packetization-mode": 1,
                            "profile-level-id": "42e01f"
                        }
                    }],
                    "encodings": [{
                        "ssrc": ssrc
                    }]
                }
            )

            producer_id = producer_response.get("id")

            if not producer_id:
                raise RuntimeError("Failed to create MediaSoup producer")

            logger.info(f"Created MediaSoup producer: {producer_id}")

            # 4. Create Producer database record
            new_producer = Producer(
                stream_id=stream_id,
                mediasoup_producer_id=producer_id,
                mediasoup_transport_id=transport_id,
                mediasoup_router_id=router_id,
                ssrc=ssrc,
                rtp_parameters=producer_response.get("rtpParameters", {}),
                state=ProducerState.ACTIVE
            )

            db.add(new_producer)

            # 5. Transition stream to LIVE
            await transition(
                stream=stream,
                to_state=StreamState.LIVE,
                reason="MediaSoup producer created and active",
                metadata={
                    "producer_id": producer_id,
                    "router_id": router_id,
                    "transport_id": transport_id
                },
                db=db
            )

            await db.commit()
            await db.refresh(new_producer)

            # Track active producer
            self.active_producers[producer_id] = {
                "stream_id": str(stream_id),
                "router_id": router_id,
                "transport_id": transport_id,
                "ssrc": ssrc,
                "created_at": datetime.now(timezone.utc)
            }

            logger.info(f"Producer {producer_id} created successfully for stream {stream_id}")

            return {
                "producer_id": str(new_producer.id),
                "mediasoup_producer_id": producer_id,
                "router_id": router_id,
                "transport_id": transport_id,
                "ssrc": ssrc,
                "state": ProducerState.ACTIVE.value,
                "stream_state": StreamState.LIVE.value
            }

        except Exception as e:
            logger.error(f"Failed to create producer for stream {stream_id}: {str(e)}")

            # Transition stream to ERROR
            await transition(
                stream=stream,
                to_state=StreamState.ERROR,
                reason=f"Producer creation failed: {str(e)}",
                metadata={"error": str(e)},
                db=db
            )
            await db.commit()

            raise RuntimeError(f"Producer creation failed: {str(e)}")

    async def close_producer(
        self,
        producer_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Close a MediaSoup producer.

        Process:
        1. Get producer from database
        2. Close MediaSoup producer (BLACK BOX)
        3. Close transport and router
        4. Update producer state to CLOSED
        5. Transition stream to STOPPED

        Args:
            producer_id: Producer UUID
            db: Database session

        Returns:
            Dict with closure details
        """
        # Get producer
        producer_query = select(Producer).where(Producer.id == producer_id)
        producer_result = await db.execute(producer_query)
        producer = producer_result.scalar_one_or_none()

        if not producer:
            raise ValueError(f"Producer {producer_id} not found")

        logger.info(f"Closing producer {producer_id} (MediaSoup: {producer.mediasoup_producer_id})")

        try:
            # Connect to MediaSoup
            await self.mediasoup_client.connect()

            # Close producer (BLACK BOX)
            await self.mediasoup_client.close_producer(producer.mediasoup_producer_id)

            # Close transport (BLACK BOX)
            await self.mediasoup_client.close_transport(producer.mediasoup_transport_id)

            # Close router (BLACK BOX)
            await self.mediasoup_client.close_router(producer.mediasoup_router_id)

            # Update producer state
            producer.state = ProducerState.CLOSED
            producer.closed_at = datetime.now(timezone.utc)

            # Update stream state
            stream_query = select(Stream).where(Stream.id == producer.stream_id)
            stream_result = await db.execute(stream_query)
            stream = stream_result.scalar_one_or_none()

            if stream and stream.state == StreamState.LIVE:
                await transition(
                    stream=stream,
                    to_state=StreamState.STOPPED,
                    reason="Producer closed",
                    metadata={"producer_id": str(producer_id)},
                    db=db
                )

            await db.commit()

            # Remove from tracking
            if producer.mediasoup_producer_id in self.active_producers:
                del self.active_producers[producer.mediasoup_producer_id]

            logger.info(f"Producer {producer_id} closed successfully")

            return {
                "producer_id": str(producer_id),
                "state": ProducerState.CLOSED.value,
                "message": "Producer closed successfully"
            }

        except Exception as e:
            logger.error(f"Error closing producer {producer_id}: {str(e)}")
            raise RuntimeError(f"Failed to close producer: {str(e)}")

    async def get_producer_stats(
        self,
        producer_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get statistics for a producer.

        Args:
            producer_id: Producer UUID
            db: Database session

        Returns:
            Dict with producer statistics
        """
        # Get producer
        producer_query = select(Producer).where(Producer.id == producer_id)
        producer_result = await db.execute(producer_query)
        producer = producer_result.scalar_one_or_none()

        if not producer:
            raise ValueError(f"Producer {producer_id} not found")

        # Get basic stats from tracking
        producer_info = self.active_producers.get(producer.mediasoup_producer_id, {})

        # Calculate uptime
        uptime_seconds = None
        if producer.created_at:
            if producer.state == ProducerState.CLOSED and producer.closed_at:
                uptime_seconds = (producer.closed_at - producer.created_at).total_seconds()
            else:
                uptime_seconds = (datetime.now(timezone.utc) - producer.created_at).total_seconds()

        return {
            "producer_id": str(producer_id),
            "mediasoup_producer_id": producer.mediasoup_producer_id,
            "state": producer.state.value,
            "ssrc": producer.ssrc,
            "stream_id": str(producer.stream_id),
            "router_id": producer.mediasoup_router_id,
            "transport_id": producer.mediasoup_transport_id,
            "uptime_seconds": int(uptime_seconds) if uptime_seconds else None,
            "created_at": producer.created_at.isoformat() if producer.created_at else None,
            "closed_at": producer.closed_at.isoformat() if producer.closed_at else None
        }

    async def get_all_active_producers(self) -> Dict[str, Any]:
        """
        Get all active producers.

        Returns:
            Dict with list of active producers
        """
        active = []

        for mediasoup_producer_id, info in self.active_producers.items():
            active.append({
                "mediasoup_producer_id": mediasoup_producer_id,
                "stream_id": info.get("stream_id"),
                "ssrc": info.get("ssrc"),
                "router_id": info.get("router_id"),
                "transport_id": info.get("transport_id"),
                "created_at": info.get("created_at").isoformat() if info.get("created_at") else None
            })

        return {
            "total_active": len(active),
            "producers": active
        }


# Global service instance
producer_service = ProducerService()
