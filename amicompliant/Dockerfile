FROM python:3.12-slim

WORKDIR /app

# Install carver-feeds-sdk from the local venv in regulatory-monitor
# In production, replace with: pip install carver-feeds-sdk
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7777

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7777"]
