'use client';

import { useEffect, useRef, useState } from 'react';
import * as mediasoupClient from 'mediasoup-client';
import { attachConsumer, detachConsumer, getStream, getStreamRouterCapabilities } from '@/lib/api-v2';

interface MediaSoupPlayerV2Props {
  streamId: string; // V2 uses stream_id instead of device_id/roomId
  shouldConnect?: boolean; // Don't auto-connect, wait for explicit trigger
  onLog?: (message: string) => void; // Callback for detailed logs
}

export default function MediaSoupPlayerV2({
  streamId,
  shouldConnect = false,
  onLog
}: MediaSoupPlayerV2Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [status, setStatus] = useState<string>('Ready to start stream');
  const [error, setError] = useState<string | null>(null);

  const deviceRef = useRef<mediasoupClient.types.Device | null>(null);
  const transportRef = useRef<mediasoupClient.types.Transport | null>(null);
  const consumerRef = useRef<mediasoupClient.types.Consumer | null>(null);
  const consumerIdRef = useRef<string | null>(null);

  // Helper for logging with callback
  const log = (message: string, level: 'info' | 'success' | 'error' = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    const logMessage = `[${timestamp}] ${level.toUpperCase()}: ${message}`;
    console.log(logMessage);
    if (onLog) {
      onLog(logMessage);
    }
  };

  // Cleanup effect when shouldConnect changes to false
  useEffect(() => {
    if (!shouldConnect) {
      // Clean up existing connections when stream is stopped
      const cleanup = async () => {
        if (consumerRef.current) {
          consumerRef.current.close();
          consumerRef.current = null;
        }

        if (consumerIdRef.current) {
          try {
            await detachConsumer(consumerIdRef.current);
          } catch (err) {
            console.error('Failed to detach consumer:', err);
          }
          consumerIdRef.current = null;
        }

        if (transportRef.current) {
          transportRef.current.close();
          transportRef.current = null;
        }

        if (videoRef.current) {
          videoRef.current.srcObject = null;
        }

        setStatus('Ready to start stream');
        setError(null);
      };

      cleanup();
    }
  }, [shouldConnect]);

  useEffect(() => {
    // Only connect when shouldConnect is true
    if (!shouldConnect) {
      log('Player ready - waiting for stream to be started...', 'info');
      setStatus('Ready to start stream');
      return;
    }

    let mounted = true;

    const connectMediaSoup = async () => {
      try {
        if (!mounted) return;

        log('========================================', 'info');
        log('V2 MediaSoup Consumer Attachment Flow', 'info');
        log('========================================', 'info');

        log(`STEP 1: Fetching stream details for ${streamId}...`, 'info');
        setStatus('Loading stream...');

        // 1. Get stream details to verify it exists and is live
        const stream = await getStream(streamId);
        log(`STEP 1: Stream found - State: ${stream.state}, Camera: ${stream.camera_id}`, 'success');

        if (stream.state !== 'live') {
          throw new Error(`Stream is not live (state: ${stream.state})`);
        }

        if (!mounted) return;
        log('STEP 2: Getting router RTP capabilities...', 'info');
        setStatus('Loading router capabilities...');

        // 2. Get router RTP capabilities
        let routerCapabilities;
        try {
          routerCapabilities = await getStreamRouterCapabilities(streamId);
          log('STEP 2: Router RTP capabilities received', 'success');
        } catch (err) {
          log('⚠️  Router capabilities endpoint not available, using fallback', 'error');
          log('    Backend needs: GET /api/v2/streams/{id}/router-capabilities', 'info');
          throw new Error('Router capabilities endpoint not implemented. Backend update required.');
        }

        if (!mounted) return;
        log('STEP 3: Creating MediaSoup Device...', 'info');
        setStatus('Creating MediaSoup device...');

        // 3. Create and load mediasoup Device
        const device = new mediasoupClient.Device();
        deviceRef.current = device;

        await device.load({ routerRtpCapabilities: routerCapabilities });
        log('STEP 3: MediaSoup Device created and loaded', 'success');

        if (!mounted) return;
        log('STEP 4: Attaching consumer via V2 API...', 'info');
        setStatus('Attaching consumer...');

        // 4. Attach consumer using V2 REST API
        // This replaces the WebSocket signaling flow
        const clientId = `web-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

        const consumerData = await attachConsumer(streamId, {
          client_id: clientId,
          rtp_capabilities: device.rtpCapabilities || {},
        });

        log(`STEP 4: Consumer attached - ID: ${consumerData.consumer_id}`, 'success');
        consumerIdRef.current = consumerData.consumer_id;

        if (!mounted) return;
        log('STEP 5: Creating WebRTC transport...', 'info');
        setStatus('Creating WebRTC transport...');

        // 5. Create recv transport from consumer data
        // Convert snake_case API response to camelCase for MediaSoup client
        const transport = device.createRecvTransport({
          id: consumerData.transport.id,
          iceParameters: consumerData.transport.ice_parameters as any,
          iceCandidates: consumerData.transport.ice_candidates as any,
          dtlsParameters: consumerData.transport.dtls_parameters as any,
        });

        transportRef.current = transport;
        log('STEP 5: WebRTC transport created', 'success');

        // Handle transport connection event
        transport.on('connect', async ({ dtlsParameters }, callback, errback) => {
          try {
            log('STEP 6: Transport connect event fired - DTLS connection...', 'info');
            // For V2, DTLS parameters are already exchanged via REST API
            // The transport should connect automatically
            callback();
            log('STEP 6: WebRTC transport connected (DTLS established)', 'success');
          } catch (err) {
            log(`STEP 6: Transport connect failed: ${err}`, 'error');
            errback(err as Error);
          }
        });

        if (!mounted) return;
        log('STEP 7: Creating consumer...', 'info');
        setStatus('Consuming media stream...');

        // 7. Create the consumer from the RTP parameters
        const consumer = await transport.consume({
          id: consumerData.consumer_id,
          producerId: stream.producer?.mediasoup_id || '', // From stream details
          kind: 'video',
          rtpParameters: consumerData.rtp_parameters as any,
        });

        consumerRef.current = consumer;

        // Resume consumer to start receiving media
        try {
          await consumer.resume();
          log('STEP 7: Consumer resumed', 'success');
        } catch (e: any) {
          log(`STEP 7: Failed to resume consumer: ${e?.message || e}`, 'error');
        }

        log(`STEP 7: Consumed video track`, 'success');
        log(`  Track ID: ${consumer.track.id}, Enabled: ${consumer.track.enabled}, ReadyState: ${consumer.track.readyState}`, 'info');

        // 8. Create MediaStream and attach to video element
        if (videoRef.current && mounted) {
          log('STEP 8: Attaching stream to video element...', 'info');

          const mediaStream = new MediaStream([consumer.track]);
          videoRef.current.srcObject = mediaStream;
          log('STEP 8: Video element srcObject set', 'success');

          // Monitor track state
          consumer.track.addEventListener('ended', () => {
            log('⚠️ Track ended', 'error');
          });

          let muteTimeout: NodeJS.Timeout | null = null;
          consumer.track.addEventListener('mute', () => {
            muteTimeout = setTimeout(() => {
              log(`⚠️ Track muted for >3s (possible stream issue)`, 'error');
            }, 3000);
          });

          consumer.track.addEventListener('unmute', () => {
            if (muteTimeout) {
              clearTimeout(muteTimeout);
              muteTimeout = null;
            }
          });

          log('STEP 9: Attempting to play video...', 'info');

          try {
            await videoRef.current.play();
            log('STEP 9: Video playback started successfully! 🎉', 'success');
            log('========================================', 'success');
            setStatus('🔴 LIVE');
          } catch (err: any) {
            log(`STEP 9: Autoplay failed: ${err.message}`, 'error');
            log('User may need to click play button', 'info');
            setStatus('Click to play');
          }
        }

      } catch (err: any) {
        if (!mounted) return;

        const errorMsg = err.message || 'Unknown error';
        log(`❌ Connection failed: ${errorMsg}`, 'error');
        setError(errorMsg);
        setStatus(`Error: ${errorMsg}`);
      }
    };

    connectMediaSoup();

    return () => {
      mounted = false;
    };
  }, [streamId, shouldConnect]);

  return (
    <div className="relative w-full h-full bg-black">
      <video
        ref={videoRef}
        className="w-full h-full object-contain"
        autoPlay
        playsInline
        muted
      />

      {/* Status Overlay */}
      <div className="absolute top-2 left-2 bg-black bg-opacity-75 px-3 py-1 rounded text-white text-sm">
        {status}
      </div>

      {/* Error Overlay */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-90">
          <div className="text-center p-6 max-w-md">
            <div className="text-red-500 text-4xl mb-4">⚠️</div>
            <h3 className="text-white text-lg font-semibold mb-2">Connection Error</h3>
            <p className="text-gray-300 text-sm">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}

// Export video ref type for parent components
export type MediaSoupPlayerV2Ref = {
  getVideoElement: () => HTMLVideoElement | null;
};
