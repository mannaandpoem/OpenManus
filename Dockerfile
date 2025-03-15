FROM python:3.12-slim

WORKDIR /app/OpenManus

RUN apt-get update && apt-get install -y git \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["bash"]
