# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies using uv
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy project
COPY . .

# Create logs directory
RUN mkdir -p logs && chmod 777 logs

# Expose the port used by Streamlit (default is 8501)
EXPOSE 8501

# No default CMD, it will be defined in docker-compose or overridden
CMD ["python", "backend/worker.py"]
