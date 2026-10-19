FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Serve the dashboard + API. Override CMD to run the CLI (e.g. the release gate).
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
