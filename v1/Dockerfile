# Multi-stage build for DigbiGPT
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY data/ ./data/

# Create startup script
RUN echo '#!/bin/bash\n\
# Start DigbiGPT API\n\
cd /app && python src/app.py\n\
' > /app/start.sh && chmod +x /app/start.sh

# Expose port
EXPOSE 9000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:9000/api/health || exit 1

# Start the service
CMD ["/app/start.sh"]