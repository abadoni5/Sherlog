FROM python:3.12-slim
WORKDIR /app
COPY fake_system/seed/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY fake_system/__init__.py fake_system/__init__.py
COPY fake_system/seed fake_system/seed
CMD ["python", "-m", "fake_system.seed.loadgen"]
