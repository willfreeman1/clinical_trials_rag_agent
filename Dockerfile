FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app
ENV PYTHONIOENCODING=utf-8
ENV MODEL_MODE=replay

COPY service/requirements.txt /app/service-requirements.txt
RUN pip install --no-cache-dir -r /app/service-requirements.txt

COPY reader /app/reader
COPY service /app/service
COPY demo /app/demo
COPY tests /app/tests

EXPOSE 8000
CMD ["python", "-m", "service.app"]
