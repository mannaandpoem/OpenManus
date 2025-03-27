FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Set environment variables
ENV PYTHONUNBUFFERED=1

# The actual installation and running will be done by the command in docker-compose.yml
CMD ["bash"]
