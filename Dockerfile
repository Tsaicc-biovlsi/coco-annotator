# syntax=docker/dockerfile:1
#
# Targets:
#   webserver  (default)  Flask API + built web client
#   workers               Celery worker (scans, imports, exports, thumbnails)
#
# Build args:
#   SAM=none|cpu|cuda     install PyTorch, Segment Anything and Ultralytics
#                         (SAM tool and pre-annotation with your YOLO models)
#   VERSION               version string shown in the UI

############################ web client ############################
FROM node:22-alpine AS client
WORKDIR /workspace/client
COPY client/package.json client/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY client/ ./
RUN npm run build

############################ python base ###########################
FROM python:3.12-slim AS python-base
ARG SAM=none
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/workspace
WORKDIR /workspace

RUN apt-get update \
 && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements-sam.txt ./
RUN pip install -r requirements.txt
# ultralytics pulls in the GUI build of OpenCV (needs libGL); keep only the
# headless one, which provides the same cv2 module.
RUN if [ "$SAM" = "cpu" ]; then \
      pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision \
      && pip install -r requirements-sam.txt; \
    elif [ "$SAM" = "cuda" ]; then \
      pip install -r requirements-sam.txt; \
    fi \
 && if [ "$SAM" != "none" ]; then \
      pip uninstall -y opencv-python opencv-python-headless \
      && pip install "opencv-python-headless==4.*"; \
    fi
# Ultralytics settings/cache in a writable place, no online checks
ENV YOLO_CONFIG_DIR=/tmp/Ultralytics YOLO_OFFLINE=1

############################ workers ###############################
FROM python-base AS workers
COPY backend/ /workspace/
CMD ["celery", "-A", "workers", "worker", "-l", "info"]

############################ webserver #############################
FROM python-base AS webserver
ARG VERSION=v1.0.0
ENV VERSION=${VERSION} DEBUG=false
COPY backend/ /workspace/
COPY --from=client /workspace/client/dist /workspace/dist
EXPOSE 5000
CMD ["gunicorn", "-c", "webserver/gunicorn_config.py", "webserver:app", "--no-sendfile"]
