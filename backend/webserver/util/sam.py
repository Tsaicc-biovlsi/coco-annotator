"""Segment Anything (SAM) integration.

The model is loaded lazily on first use so the webserver starts quickly and
still runs when PyTorch / the checkpoint are not installed.  Image embeddings
are the expensive part of SAM, so the embeddings of the most recently used
images are cached: once an image is embedded, every extra click is cheap.
"""
import logging
import os
import threading
from collections import OrderedDict

import cv2
import numpy as np
from PIL import Image

from config import Config

logger = logging.getLogger('gunicorn.error')


def mask_to_polygons(mask, min_area=10, epsilon=1.0):
    """Convert a binary mask into COCO polygon segmentation lists."""
    mask = np.ascontiguousarray(mask.astype(np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    polygons = []
    for contour in contours:
        if cv2.contourArea(contour) < min_area:
            continue
        if epsilon > 0:
            contour = cv2.approxPolyDP(contour, epsilon, True)
        if len(contour) < 3:
            continue
        polygons.append(contour.reshape(-1).astype(float).tolist())
    return polygons


class SamService:

    def __init__(self, checkpoint, model_type, device, cache_size=4):
        self.checkpoint = checkpoint
        self.model_type = model_type
        self.device = device
        self.cache_size = cache_size

        self._lock = threading.Lock()
        self._predictor = None
        self._error = None
        self._cache = OrderedDict()  # image_id -> predictor features
        self._current = None         # image_id currently set on predictor

    @property
    def available(self):
        if not os.path.isfile(self.checkpoint):
            return False
        try:
            import torch  # noqa: F401
            import segment_anything  # noqa: F401
        except ImportError:
            return False
        return self._error is None

    def status(self):
        return {
            "available": self.available,
            "loaded": self._predictor is not None,
            "model_type": self.model_type,
            "error": self._error,
        }

    def _load(self):
        if self._predictor is not None:
            return self._predictor

        import torch
        from segment_anything import sam_model_registry, SamPredictor

        device = self.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(f"Loading SAM ({self.model_type}) from {self.checkpoint} on {device}")
        try:
            sam = sam_model_registry[self.model_type](checkpoint=self.checkpoint)
            sam.to(device=device)
            self._predictor = SamPredictor(sam)
        except Exception as e:  # pragma: no cover - depends on weights
            self._error = str(e)
            raise
        return self._predictor

    def _set_image(self, predictor, image_id, path):
        if self._current == image_id:
            return

        cached = self._cache.get(image_id)
        if cached is not None:
            self._cache.move_to_end(image_id)
            (predictor.features, predictor.original_size,
             predictor.input_size) = cached
            predictor.is_image_set = True
        else:
            image = np.array(Image.open(path).convert("RGB"))
            predictor.set_image(image)
            self._cache[image_id] = (
                predictor.features, predictor.original_size, predictor.input_size
            )
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        self._current = image_id

    def prepare(self, image_id, path):
        """Compute (and cache) the image embedding ahead of the first click."""
        with self._lock:
            predictor = self._load()
            self._set_image(predictor, image_id, path)

    def prepare_async(self, image_id, path):
        def run():
            try:
                self.prepare(image_id, path)
            except Exception:  # pragma: no cover - logged for the operator
                logger.exception("SAM prepare failed")
        threading.Thread(target=run, daemon=True).start()

    def predict(self, image_id, path, points=None, labels=None, box=None,
                multimask=False):
        """Return (polygons, score, area) for the given prompts.

        points: [[x, y], ...] in image pixel coordinates
        labels: [1|0, ...]  1 = foreground, 0 = background
        box:    [x1, y1, x2, y2] in image pixel coordinates
        """
        with self._lock:
            predictor = self._load()
            self._set_image(predictor, image_id, path)

            point_coords = np.array(points, dtype=np.float32) if points else None
            point_labels = None
            if point_coords is not None:
                point_labels = np.array(labels if labels else [1] * len(points),
                                        dtype=np.int32)
            box_arr = np.array(box, dtype=np.float32) if box else None

            # With a single point SAM is ambiguous; ask for 3 masks and keep best
            multimask = multimask or (box_arr is None and point_coords is not None
                                      and len(point_coords) == 1)

            masks, scores, _ = predictor.predict(
                point_coords=point_coords,
                point_labels=point_labels,
                box=box_arr,
                multimask_output=multimask,
            )

        best = int(np.argmax(scores))
        mask = masks[best]
        return mask_to_polygons(mask), float(scores[best]), int(mask.sum())


sam = SamService(
    checkpoint=Config.SAM_CHECKPOINT,
    model_type=Config.SAM_MODEL_TYPE,
    device=Config.SAM_DEVICE,
    cache_size=Config.SAM_CACHE_SIZE,
)
