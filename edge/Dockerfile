FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ src/

# Create data directory for SQLite spool persistence
RUN mkdir -p /data

CMD ["python", "-m", "src.main"]
