# Upgrading to coco-annotator 1.0 (2026 modernisation)

This release moves every part of the stack off end-of-life software, replaces
the TensorFlow 1 AI tools with Segment Anything, and adds a rotated bounding
box tool.

## What changed

| Part | Before | Now |
|---|---|---|
| Frontend framework | Vue 2.5, Vuex 3, Vue Router 3 | **Vue 3.5**, Vuex 4, Vue Router 4 |
| Frontend build | Vue CLI 3 (webpack 4), Node 10 | **Vite 7**, Node 22 |
| Frontend tests | Jest 24 | Vitest |
| Python | 3.6 (TensorFlow 1.14 image) | **3.12** (`python:3.12-slim`) |
| Web framework | Flask 1.0, flask-restplus 0.12 (dead) | **Flask 3.1, flask-restx 1.3** |
| Realtime | Flask-SocketIO 3 + eventlet, vue-socket.io | Flask-SocketIO 5 (threading + simple-websocket), socket.io-client 4 |
| Task queue | Celery 4.2 | **Celery 5.5** |
| Database | MongoDB 4.0 | **MongoDB 7.0** (see migration below) |
| Message broker | RabbitMQ 3.7 | RabbitMQ 4.1 |
| AI assistance | DEXTR + Mask R-CNN (Keras 2.1 / TF 1.14) | **Segment Anything (PyTorch)** |
| Image libs | OpenCV 4.0, imantics, Pillow 5 | OpenCV 4.x headless, NumPy 2, Shapely 2, Pillow 11 |

## New features

### Rotated bounding boxes (`O`)

Select an annotation, pick the **Rotated BBox** tool (↻ icon or `O`), then
draw a box with three clicks:

1. click the first corner,
2. click the second corner — these two points are one edge of the box (its
   direction and length; you can also drag from the first point to the
   second; hold **Shift** to snap the angle, 15° by default),
3. move the mouse to set the width and click to finish (**Esc** cancels).

Edit the selected box by dragging the round handle (rotate, **Shift** snaps),
a corner (resize, the opposite corner stays fixed) or the inside (move).
Arrow keys move it by 1 px (**Shift**: 10 px). Like a BBox, it can also be
moved or resized with the **Select** tool (`S`); it stays a rectangle.
The thicker edge shows the box's *heading* (first edge); *Swap Heading*
rotates the corner order by 90° without moving the box. While this tool or
SAM is active, clicking an existing shape does not select it (so you can
draw over other objects); pick annotations from the sidebar or with `S`.

Stored and exported per annotation:

```json
"isrbbox": true,
"rbbox": [cx, cy, w, h, angle],
"segmentation": [[x1, y1, x2, y2, x3, y3, x4, y4]]
```

`angle` is in degrees, clockwise in image coordinates (y down), measured along
the first edge (corner 1 → 2), normalised to (-180, 180]. `w` is the first
edge, `h` the second. The polygon keeps the corners in that order, so tools
that only understand COCO polygons still work. `bbox`/`area` are filled as
usual. COCO imports may contain `rbbox` without a polygon (e.g. converted from
DOTA); the polygon is generated.

To train oriented detectors:

```bash
python scripts/export_obb.py coco-export.json labels/ --format dota       # DOTA txt
python scripts/export_obb.py coco-export.json labels/ --format yolo-obb   # Ultralytics YOLO-OBB
```

### Segment Anything (`A`)

Select an annotation, pick the **SAM** tool (◎ icon or `A`):

* click the object (green point), **Shift**+click to exclude background (red),
* or drag a box around the object,
* press **Enter** (or *Apply*) to add the preview to the annotation.

The image embedding is computed once when the tool is selected and cached on
the server, so later clicks are fast (~50 ms). On CPU the first embedding of
an image takes a few seconds with `vit_b`; a GPU makes it near-instant.

Enable it:

```bash
./models/download_sam.sh            # vit_b checkpoint into ./models
SAM=cpu docker compose up -d --build                          # CPU
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build   # NVIDIA GPU
```

Without PyTorch or the checkpoint the tool is simply disabled.

## Migrating an existing installation

### 1. MongoDB data (required)

MongoDB 7 cannot open a data directory written by MongoDB 4.0. Copy the data
with a dump/restore (the old volume is only read):

```bash
docker compose down                                   # stop the old stack
docker volume ls | grep mongodb_data                  # find the old volume name
OLD_VOLUME=coco-annotator_mongodb_data NEW_VOLUME=coco-annotator_mongodb7 \
  ./scripts/migrate_mongo.sh
```

Then point the `database` service in `docker-compose.yml` at `NEW_VOLUME`
(declare it as `external: true`). If you prefer not to migrate yet, set the
image back to `mongo:4.4` — the application works with MongoDB 4.4+ — but
note 4.x is end-of-life.

### 2. Images are built locally

The compose files no longer pull the old `jsbroks/coco-annotator:*` images.
`docker compose up -d --build` builds the `webserver` and `workers` targets
of the root `Dockerfile`.

### 3. Configuration

Removed environment variables: `MASK_RCNN_FILE`, `MASK_RCNN_CLASSES`,
`DEXTR_FILE`.

New ones:

| Variable | Default | Meaning |
|---|---|---|
| `SAM_MODEL_TYPE` | `vit_b` | `vit_b`, `vit_l` or `vit_h` |
| `SAM_CHECKPOINT` | `/models/sam_vit_b_01ec64.pth` | checkpoint path |
| `SAM_DEVICE` | `auto` | `auto`, `cpu` or `cuda` |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | run tasks in the web process (development) |
| `VERSION` | git tag | version shown in the UI |

`FILE_WATCHER=false` and `TESTING=false` are now honoured (previously any
non-empty value enabled them).

### 4. Users

Passwords stored by the old version (`sha256$…`) are still accepted and are
re-hashed with scrypt on the user's next login. No action needed.

### 5. Removed features / API

* `POST /api/model/dextr/<id>` and `POST /api/model/maskrcnn` → replaced by
  `POST /api/model/sam/<image_id>` (`points`, `labels`, `box`) and
  `POST /api/model/sam/<image_id>/prepare`. `GET /api/model/` reports what is
  available. The **Annotate Image** button (dataset "annotate URL") still
  works with any external model server that returns COCO.
* `POST /api/dataset/<id>/generate` (Google Images download) — the library it
  used stopped working years ago.

## Bugs fixed along the way

* Celery tasks (scan, import, export, thumbnails) were bound to a thread-local
  app; with a multi-threaded web server they were sent to the wrong broker.
* The file watcher thread died on the first half-written image.
* `Esc` in the annotator threw (`bbox.deletePolygon` did not exist).
* `GET /api/dataset/coco/<id>` referenced a model that no longer existed.
* Editing a category with a duplicate name raised `NameError`.
* Export download file names contained `b'…'`.
* `Dataset.vue` referenced an undefined `process` variable (worked only
  because webpack 4 injected a Node `process` shim).
* paper.js is loaded as a classic script: bundled as an ES module it runs in
  strict mode and throws while styling groups.

## Development

```bash
docker compose -f docker-compose.dev.yml up --build   # http://localhost:8080 (hot reload)

# or without Docker
cd backend && pip install -r requirements.txt mongomock && pytest   # no MongoDB/RabbitMQ needed
cd client && npm ci && npm run dev && npm test
```

Backend tests run against an in-memory MongoDB and execute Celery tasks
eagerly (`tests/conftest.py`), including an end-to-end API smoke test
(`tests/test_smoke.py`).

## Not changed (yet)

* **Bootstrap 4.6 + jQuery** are kept for the existing modals and dropdowns;
  Bootstrap 4 is end-of-life and moving to Bootstrap 5 is the next step.
* The REST API and the URL scheme (`/#/annotate/<id>`) are unchanged.
