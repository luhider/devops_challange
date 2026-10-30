FROM python:3.11-slim

# Prevent python from writing pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create dedicated unprivileged non-root user and group
# Ensure /tmp/trt_cache exists and has write permissions
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -M appuser && \
    mkdir -p /app /tmp/trt_cache && \
    chown -R appuser:appgroup /app /tmp/trt_cache && \
    chmod 777 /tmp/trt_cache

# Copy application modules and default model artifacts with non-root ownership
COPY --chown=appuser:appgroup vision_api /app/vision_api
COPY --chown=appuser:appgroup inference_worker /app/inference_worker
COPY --chown=appuser:appgroup models /app/models

# Run as non-root user
USER 10001:10001

EXPOSE 8000 9000

CMD ["python", "vision_api/app.py"]
