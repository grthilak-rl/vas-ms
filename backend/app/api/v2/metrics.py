"""
Metrics API - Prometheus metrics export endpoint

Provides /v2/metrics endpoint for Prometheus scraping.
"""
from fastapi import APIRouter, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from loguru import logger
from datetime import datetime, timezone

from database import get_db
from app.metrics.prometheus import (
    get_prometheus_metrics,
    get_prometheus_content_type,
    metrics_collector
)
from app.models.stream import Stream, StreamState
from app.models.producer import Producer, ProducerState
from app.models.consumer import Consumer, ConsumerState
from app.services.stream_ingestion_service import stream_ingestion_service

router = APIRouter(tags=["Metrics"])


@router.get("/metrics")
async def prometheus_metrics(db: AsyncSession = Depends(get_db)):
    """
    Prometheus metrics endpoint.

    This endpoint is scraped by Prometheus to collect metrics.
    No authentication required for metrics endpoint (typically restricted by network).

    Returns:
        Prometheus text format metrics
    """
    try:
        # Update stream metrics
        stream_counts = {}
        for state in StreamState:
            count_query = select(func.count(Stream.id)).where(Stream.state == state)
            result = await db.execute(count_query)
            stream_counts[state.value] = result.scalar()

        await metrics_collector.update_stream_metrics(stream_counts)

        # Update stream uptime for LIVE streams
        live_streams_query = select(Stream).where(Stream.state == StreamState.LIVE)
        live_streams_result = await db.execute(live_streams_query)
        live_streams = live_streams_result.scalars().all()

        for stream in live_streams:
            if stream.started_at:
                uptime = int((datetime.now(timezone.utc) - stream.started_at).total_seconds())
                await metrics_collector.update_stream_uptime(
                    str(stream.id),
                    stream.name,
                    uptime
                )

        # Update producer metrics
        producer_counts = {}
        for state in ProducerState:
            count_query = select(func.count(Producer.id)).where(Producer.state == state)
            result = await db.execute(count_query)
            producer_counts[state.value] = result.scalar()

        await metrics_collector.update_producer_metrics(producer_counts)

        # Update consumer metrics
        consumer_counts = {}
        for state in ConsumerState:
            count_query = select(func.count(Consumer.id)).where(Consumer.state == state)
            result = await db.execute(count_query)
            consumer_counts[state.value] = result.scalar()

        await metrics_collector.update_consumer_metrics(consumer_counts)

        # Update active consumers per stream
        active_consumers_query = select(
            Consumer.stream_id,
            func.count(Consumer.id)
        ).where(
            Consumer.state.in_([ConsumerState.CONNECTING, ConsumerState.CONNECTED])
        ).group_by(Consumer.stream_id)

        active_consumers_result = await db.execute(active_consumers_query)
        active_consumers_per_stream = active_consumers_result.all()

        for stream_id, count in active_consumers_per_stream:
            await metrics_collector.update_active_consumers_per_stream(str(stream_id), count)

        # Update FFmpeg health metrics
        all_ingestions = await stream_ingestion_service.get_all_active_ingestions()
        healthy_ffmpeg_count = 0

        for ingestion in all_ingestions.get("streams", []):
            health = ingestion.get("health", {})

            if health.get("is_healthy"):
                healthy_ffmpeg_count += 1

                # Update FFmpeg resource metrics
                cpu_percent = health.get("cpu_percent", 0)
                memory_mb = health.get("memory_mb", 0)
                stream_id = health.get("stream_id")

                if stream_id:
                    await metrics_collector.update_ffmpeg_metrics(
                        stream_id,
                        cpu_percent,
                        memory_mb
                    )

        await metrics_collector.update_ffmpeg_health_count(healthy_ffmpeg_count)

        # Get metrics in Prometheus format
        metrics_data = get_prometheus_metrics()

        return Response(
            content=metrics_data,
            media_type=get_prometheus_content_type()
        )

    except Exception as e:
        logger.error(f"Error generating Prometheus metrics: {str(e)}")
        # Return empty metrics on error (Prometheus will mark scrape as failed)
        return Response(
            content=b"",
            media_type=get_prometheus_content_type()
        )
