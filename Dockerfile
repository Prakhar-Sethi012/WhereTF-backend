# syntax=docker/dockerfile:1

FROM python:3.11-slim

WORKDIR /app

# Set a build argument (default to CPU mode to save space)
ARG USE_GPU=0

COPY requirements.txt .

# Dynamically install PyTorch based on the USE_GPU flag
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ "$USE_GPU" = "1" ] ; then \
        echo "Building for GPU..." && \
        pip install -r requirements.txt ; \
    else \
        echo "Building for CPU..." && \
        pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt ; \
    fi

# Download NLTK data separately so it gets cached
RUN python -m nltk.downloader punkt punkt_tab wordnet omw-1.4

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]