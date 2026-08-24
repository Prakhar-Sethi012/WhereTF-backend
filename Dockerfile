# syntax=docker/dockerfile:1

FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies separately so this layer is cached
# unless requirements.txt changes.
COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt
    RUN python -m nltk.downloader punkt punkt_tab wordnet omw-1.4

# Copy application code after dependencies
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]