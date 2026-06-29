# payments demo service.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY payments ./payments
COPY tests ./tests
COPY pytest.ini .

EXPOSE 8080

# Single worker so the in-process pool and its metrics reflect one pool instance.
CMD ["uvicorn", "payments.api:app", "--host", "0.0.0.0", "--port", "8080"]
