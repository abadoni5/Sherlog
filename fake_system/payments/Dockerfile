# Build from the repo root:  docker build -f fake_system/payments/Dockerfile .
FROM python:3.12-slim
WORKDIR /app
COPY fake_system/payments/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY fake_system/__init__.py fake_system/__init__.py
COPY fake_system/common fake_system/common
COPY fake_system/payments fake_system/payments
CMD ["uvicorn", "fake_system.payments.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
