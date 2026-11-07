# Build from the repo root:  docker build -f fake_system/inventory/Dockerfile .
FROM python:3.12-slim
WORKDIR /app
COPY fake_system/inventory/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY fake_system/__init__.py fake_system/__init__.py
COPY fake_system/common fake_system/common
COPY fake_system/inventory fake_system/inventory
CMD ["uvicorn", "fake_system.inventory.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
