FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/model_service

COPY model_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY model_service/ ./

EXPOSE 9000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
