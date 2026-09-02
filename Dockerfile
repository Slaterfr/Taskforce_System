FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .



# Create instance directory for SQLite database and set permissions
RUN mkdir -p instance && \
    useradd -m appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Use start script to run both services
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]


