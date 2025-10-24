# Multi-stage build for DigbiGPT system
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY poc/requirements.txt requirements_claims.txt
COPY ai-agent-service/requirements.txt requirements_ai.txt

# Install claims server dependencies
RUN pip install --no-cache-dir -r requirements_claims.txt

# Install ai-agent-service dependencies
RUN pip install --no-cache-dir -r requirements_ai.txt

# Copy application code
COPY poc/ ./poc/
COPY ai-agent-service/ ./ai-agent-service/
COPY claims.db ./claims.db
COPY digbigpt_api.py ./

# Create startup script
RUN echo '#!/bin/bash\n\
# Start claims server in background\n\
cd /app/poc && python3 server.py &\n\
\n\
# Wait for claims server to start\n\
sleep 5\n\
\n\
# Start DigbiGPT API\n\
cd /app && python3 digbigpt_api.py\n\
' > /app/start.sh && chmod +x /app/start.sh

# Expose ports
EXPOSE 8000 8811

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start both services
CMD ["/app/start.sh"]
