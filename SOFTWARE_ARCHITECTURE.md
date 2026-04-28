# B1 Edge Software Architecture Breakdown

To allow three different developers to work in parallel without stepping on each other's toes, the Python pipeline is divided into three distinct, independent sub-layers. 

Each person is responsible for their own layer, ensuring clear inputs and outputs between them.

---

## 1. YOLO Layer (Detection & Tracking)
**Owner:** Developer 1

This layer acts as the **"Brain"**. It is responsible for interacting with the raw camera feeds and running the heavy machine learning models.

* **Input:** Raw video frames from OpenCV (USB or IP cameras).
* **Responsibilities:**
  * Apply `FRAME_SKIP` logic to save processing power.
  * Run **YOLOv8n** to detect objects (cars, buses, trucks, motorcycles, pedestrians).
  * Filter out detections below the `CONFIDENCE_THRESHOLD`.
  * Pass bounding boxes to **ByteTrack** to assign a stable, consistent `vehicle_id` across frames.
  * Calculate the speed of the vehicle (km/h) based on how far the centroid moves between frames.
* **Output:** A raw python list/dictionary of tracked objects per frame.
  *(Example: `[{'vehicle_id': 'veh_203', 'class': 'car', 'confidence': 0.93, 'bbox': {'x':412,'y':178,'w':82,'h':46}, 'centroid': {'x':453,'y':201}, 'speed': 34.2}]`)*

---

## 2. Serializing & Enrichment Layer
**Owner:** Developer 2

This layer acts as the **"Translator"**. It takes the raw, unstructured pixel coordinates from the YOLO layer and turns them into meaningful, enriched business data.

* **Input:** The raw list of tracked objects from Layer 1, plus the `lanes.json` configuration file.
* **Responsibilities:**
  * Load `lanes.json` into memory to understand the physical layout of the junction.
  * Map each vehicle's `(x, y)` centroid to a specific `lane_id` using mathematical point-in-polygon logic.
  * Structure the data into a strict JSON dictionary that matches the exact **Software Requirements Specification (SRS)** format the L2 team expects.
* **Output:** A cleanly formatted, final JSON event dictionary matching this strict schema:
```json
{
 "camera_id": "cam_north_approach",
 "timestamp": "2026-04-16T10:15:23.456Z",
 "frame_id": 18422,
 "vehicle_id": "veh_203",
 "class": "car",
 "confidence": 0.93,
 "bbox": { "x": 412, "y": 178, "w": 82, "h": 46 },
 "centroid": { "x": 453, "y": 201 },
 "lane_id": 1,
 "speed_estimate": 34.2
}
```

---

## 3. Kafka Producer & Resilience Layer
**Owner:** Developer 3

This layer acts as the **"Delivery Mechanism"**. It does no data processing; its sole job is to guarantee that the JSON events safely reach the cloud broker (Kafka), even during severe network outages.

* **Input:** The structured JSON event dictionary from Layer 2.
* **Responsibilities:**
  * Maintain a persistent producer connection to the Kafka broker (`KAFKA_BROKERS`).
  * Publish the JSON events to the `traffic.events.raw` topic, ensuring they arrive within 500ms of detection.
  * Monitor the network. If Kafka drops or goes offline, intercept the JSON events and save them instantly to a local **SQLite offline buffer** database (`BUFFER_DB_PATH`).
  * When Kafka returns online, silently read the stored SQLite events and replay them to the broker in chronological order so no data is ever lost.
* **Output:** Network transmission to Kafka, and local SQLite disk writes.
