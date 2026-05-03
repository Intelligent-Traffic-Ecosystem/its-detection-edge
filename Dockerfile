# Use an official Python runtime as a parent image
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Set the working directory in the container
WORKDIR /app

# Install system dependencies for OpenCV, GStreamer, and Kafka
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    ffmpeg \
    gstreamer1.0-tools \
    gstreamer1.0-libav \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    librdkafka1 \
    librdkafka-dev \
    pkg-config \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.3.1 torchvision==0.18.1 \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir confluent-kafka

# Copy the current directory contents into the container at /app
COPY . .

# Run main.py when the container launches
CMD ["python", "-m", "src.main"]