# Balena Fleet Config (Pi 5)

## Fleet and device setup
1. Create a new fleet in BalenaCloud for Raspberry Pi 5.
2. Download the BalenaOS image for the fleet, flash it to the SD card, and boot the Pi 5.
3. Wait for the device to show as online in the fleet.

## Compose file
The Balena multi-container layout is defined in [docker-compose.yml](docker-compose.yml).

## Fleet variables (global)
Set these as fleet-wide variables in BalenaCloud:
- KAFKA_BROKERS (required, example: broker1:9092,broker2:9092)
- KAFKA_TOPIC (optional, default: traffic.events.raw)
- KAFKA_SECURITY_PROTOCOL (optional, example: SASL_SSL)
- KAFKA_SASL_MECHANISM (optional, example: PLAIN)
- KAFKA_USERNAME (optional, secret)
- KAFKA_PASSWORD (optional, secret)
- KAFKA_SSL_CA (optional, path inside container to CA file)

## Service variables (per camera service)
Set these as service variables for each service (edge-camera-1, edge-camera-2):
- CAMERA_URL (required, secret if it contains credentials)
- LANES_CONFIG_PATH (optional, example: config/lanes_cam_01.json)
- BUFFER_DB_PATH (optional, example: /data/cam_01/offline_buffer.db)
- API_PORT (optional, defaults are set in compose)

The compose file already sets CAMERA_ID for each service. Override it only if you need custom names.

## Camera URL examples
- USB camera: /dev/video0 (or /dev/video1)
- RTSP camera: rtsp://user:pass@host:554/stream

## Secrets
Mark CAMERA_URL, KAFKA_USERNAME, and KAFKA_PASSWORD as secrets in the BalenaCloud dashboard.

## Notes
- Each service writes its offline buffer under /data for persistence.
- If you use separate lane files per camera, update LANES_CONFIG_PATH for each service.
- If you use RTSP-only cameras, remove the devices section in docker-compose.yml.
