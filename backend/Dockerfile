# 1. Use an official, lightweight Python runtime blueprint
FROM python:3.11-slim

# 2. Create and set the working directory inside the container
WORKDIR /workspace

# 3. Stop Python from writing .pyc files and buffering logs (standard Docker optimization)
ENV PYTHONTONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 4. Install essential tools needed for system packages like bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy requirements.txt first to take advantage of Docker caching
COPY requirements.txt .

# 6. Upgrade pip and install all Python packages smoothly
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 7. Copy the rest of your ResearchMind application code
COPY . .

# 8. Create the directory where uploaded PDFs will stay locally inside the container
RUN mkdir -p uploads

# 9. Expose port 8000 so we can talk to the container from outside
EXPOSE 8000

# 10. The command that starts your server inside the container
# 0.0.0.0 tells Uvicorn to listen to all incoming network interfaces
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]