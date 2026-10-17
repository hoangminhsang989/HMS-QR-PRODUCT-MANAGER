FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HMS_QR_TEST_ROOT=/tmp/hms-runtime \
    HMS_QR_ENV=dev

RUN mkdir -p /tmp/hms-runtime/db /tmp/hms-runtime/storage

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8000

CMD ["uvicorn", "apps.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
