FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application modules (GUI is not used in Docker; CLI runner only)
COPY app_config.py launcher_core.py create_instance.py ./

# config.json is provided at runtime via a volume mount (see docker-compose.yml)
CMD ["python", "create_instance.py"]
