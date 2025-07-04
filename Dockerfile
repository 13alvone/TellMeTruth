# Use an official Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (ffmpeg is required)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN python3 -m pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your app code
COPY . .

# Make sure scripts are executable (for shell scripts)
RUN chmod +x /app/setup.sh /app/run_all_pipeline.sh

# Default command - run the pipeline (override for manual/script testing)
CMD ["bash", "/app/run_all_pipeline.sh"]

