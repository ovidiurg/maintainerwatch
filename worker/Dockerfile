FROM python:3.12-slim

WORKDIR /worker
COPY requirements.txt /worker/requirements.txt
RUN pip install --no-cache-dir -r /worker/requirements.txt
COPY app.py /worker/app.py

# Run behind an isolated gVisor/Kata container. The configured
# DYNAMIC_SANDBOX_COMMAND is responsible for detonating a package.
ENV PYTHONUNBUFFERED=1
EXPOSE 8090
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
