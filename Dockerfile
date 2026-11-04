FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN apt-get update \
    && apt-get install -y gcc libpq-dev \
    && apt-get clean

# Copy uv from the official Astral image (this is the cleanest way to install it)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependencies and install using uv
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy the actual application code
COPY ./app /app/app