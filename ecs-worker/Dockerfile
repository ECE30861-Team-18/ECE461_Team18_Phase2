FROM python:3.11-slim

WORKDIR /app

RUN pip install boto3

COPY worker.py .
COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "worker.py"]
