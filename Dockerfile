# Build stage: install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install deps in an isolated layer so code changes don't bust the cache.
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --retries=10 -r requirements.txt


# Runtime stage: copy application code
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from the builder stage.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source.
COPY src/ ./src/

# Copy the trained model artifact — required at runtime by src/models/predict.py.
COPY saved_models/ ./saved_models/

# Copy fraud playbook knowledge base — required at runtime by the RAG retriever.
COPY data/knowledge/ ./data/knowledge/

# Copy remaining project files needed at runtime.
# alembic/ and alembic.ini are included so migrations can be run inside the container.
COPY alembic/ ./alembic/
COPY alembic.ini .

# Run as a non-root user.
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Use exec form so the process receives OS signals (e.g. SIGTERM) directly.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
