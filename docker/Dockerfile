FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# System deps + LibreOffice + Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    libreoffice-impress \
    libreoffice-writer \
    libreoffice-calc \
    python3 \
    python3-pip \
    python3-venv \
    python3-uno \
    ca-certificates \
    fontconfig \
    fonts-dejavu \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libmupdf-dev \
    libfreetype6-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Node.js 22 LTS + pptxgenjs for presentation generation
RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
  && apt-get install -y --no-install-recommends nodejs \
  && npm install -g pptxgenjs \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Chromium for HTML rendering + image tools + fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 \
    imagemagick ghostscript poppler-utils \
    libcairo2-dev pkg-config \
    fonts-noto fonts-roboto fonts-open-sans fonts-lato \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create venv with system-site-packages for uno access
RUN python3 -m venv --system-site-packages /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime deps
RUN pip install --no-cache-dir \
  fastapi uvicorn[standard] python-multipart pymupdf prometheus-client ujson \
  unoserver "redis[hiredis]>=5.0.0"

# Content agent deps
RUN pip install --no-cache-dir \
  matplotlib cairosvg svglib reportlab pandas openpyxl \
  jinja2 playwright python-pptx \
  "deepagents==0.5.8" "langchain-openai>=0.2.0" \
  "litellm==1.83.7" "langchain-litellm==0.6.5" \
  && playwright install chromium

WORKDIR /app
COPY src/ ./src/
COPY pyproject.toml README.md PROJECT.md ./

# Install the officeplane package
RUN pip install --no-cache-dir -e .

# Copy Prisma schema
COPY prisma/ ./prisma/

# Non-root user
RUN useradd -m -u 10001 appuser
RUN mkdir -p /data /data/workspaces && chown -R appuser:appuser /data /app /opt/venv
USER appuser

# Generate Prisma client as appuser to avoid permission issues
RUN python -m prisma generate

EXPOSE 8001
ENV DATA_DIR=/data
ENV OUTPUT_MODE=inline
ENV OFFICEPLANE_DRIVER=libreoffice
ENV POOL_SIZE=6
ENV CONVERT_TIMEOUT_SEC=45
ENV LOG_FORMAT=json

CMD ["uvicorn", "officeplane.api.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--loop", "uvloop"]
