# Use a stable Python image (Debian-based, with arm64 support on Apple Silicon)
FROM python:3.11-slim

# Avoid .pyc files and buffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Workdir inside the container
WORKDIR /app

# OS-level deps:
# - build-essential, cmake: build C/C++ deps when needed
# - poppler-utils: for pdf2image
# - tesseract-ocr, libtesseract-dev: for pytesseract OCR
# - libgl1, libglib2.0-0: for image/GUI libs used by some packages
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    poppler-utils \
    tesseract-ocr \
    libtesseract-dev \
    libgl1 \
    libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (better layer caching)
COPY requirements.txt .

# Install Python dependencies
# 1) Upgrade pip
# 2) Pre-install pyarrow from wheel (avoid building from source)
# 3) Install the rest from requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir "pyarrow>=16.0.0" && \
    python -m pip install --no-cache-dir -r requirements.txt

# Now copy the whole app into the image
COPY . .

# Streamlit will serve on 8501
EXPOSE 8501

# NOTE: we do NOT set OPENAI_API_KEY here to avoid leaking secrets.
# You'll pass it at `docker run` time.

# Start the Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]