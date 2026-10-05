"""Pre-annotation with your own Ultralytics YOLO models.

Put trained ``.pt`` files in the models folder (``MODELS_DIR`` on the host,
``/models`` in the container). Every ``.pt`` file there is offered in the UI.
Detect, OBB (rotated boxes), segment and pose models are supported; their
predictions are converted to this annotator's annotation format:

* detect  -> BBox annotation (4-corner polygon, ``isbbox``)
* obb     -> rotated box (4 corners in order, ``isrbbox`` + ``rbbox``)
* segment -> polygon annotation
* pose    -> BBox annotation with COCO ``keypoints``

Model classes are matched to the dataset's categories by name (ignoring
case). Missing categories can be created and added to the dataset.

Models are loaded lazily, cached, and run one prediction at a time per
server (a single GPU is shared by all users).
"""
import logging
import os
import threading
from collections import OrderedDict

import numpy as np

from config import Config
from geometry import polygon_to_rbbox
# COCO person keypoints / skeleton (17-keypoint pose models)
from geometry.yolo_format import COCO_KEYPOINTS, COCO_SKELETON

logger = logging.getLogger('gunicorn.error')

# Keypoints whose confidence is below this are stored as "not labelled".
KEYPOINT_MIN_CONF = 0.5


def _polygon_area(flat):
    pts = np.asarray(flat, dtype=float).reshape(-1, 2)
    x, y = pts[:, 0], pts[:, 1]
    return float(abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) / 2)


def _bbox_of(flat):
    pts = np.asarray(flat, dtype=float).reshape(-1, 2)
    x1, y1 = pts.min(axis=0)
    x2, y2 = pts.max(axis=0)
    return [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]


def _box_polygon(x1, y1, x2, y2):
    return [x1, y1, x2, y1, x2, y2, x1, y2]


def _round(values, digits=2):
    return [round(float(v), digits) for v in values]


def result_to_predictions(result, names):
    """Convert one ultralytics ``Results`` object to annotation dicts."""
    predictions = []

    def base(cls, score):
        cls = int(cls)
        return {"class_id": cls, "class_name": str(names.get(cls, cls)),
                "score": round(float(score), 4)}

    # Rotated boxes
    obb = getattr(result, "obb", None)
    if obb is not None and len(obb):
        corners = obb.xyxyxyxy.cpu().numpy()
        for pts, cls, score in zip(corners, obb.cls.cpu().numpy(), obb.conf.cpu().numpy()):
            polygon = _round(pts.reshape(-1))
            p = base(cls, score)
            p.update({
                "type": "obb",
                "segmentation": [polygon],
                "isrbbox": True,
                "rbbox": [round(v, 2) for v in polygon_to_rbbox(polygon)],
                "bbox": _bbox_of(polygon),
                "area": _polygon_area(polygon),
            })
            predictions.append(p)
        return predictions

    boxes = getattr(result, "boxes", None)
    if boxes is None or not len(boxes):
        return predictions

    xyxy = boxes.xyxy.cpu().numpy()
    classes = boxes.cls.cpu().numpy()
    scores = boxes.conf.cpu().numpy()

    masks = getattr(result, "masks", None)
    mask_polygons = masks.xy if masks is not None else None

    keypoints = getattr(result, "keypoints", None)
    kp_data = keypoints.data.cpu().numpy() if keypoints is not None else None

    for i, ((x1, y1, x2, y2), cls, score) in enumerate(zip(xyxy, classes, scores)):
        p = base(cls, score)
        box = _round(_box_polygon(x1, y1, x2, y2))

        if mask_polygons is not None:
            pts = np.asarray(mask_polygons[i])
            if len(pts) >= 3:
                polygon = _round(pts.reshape(-1))
                p.update({
                    "type": "segment",
                    "segmentation": [polygon],
                    "isbbox": False,
                    "bbox": _bbox_of(polygon),
                    "area": _polygon_area(polygon),
                })
                predictions.append(p)
                continue
            # degenerate mask: fall back to the box

        p.update({
            "type": "pose" if kp_data is not None else "detect",
            "segmentation": [box],
            "isbbox": True,
            "bbox": _bbox_of(box),
            "area": _polygon_area(box),
        })

        if kp_data is not None:
            flat = []
            for kp in kp_data[i]:
                x, y = float(kp[0]), float(kp[1])
                conf = float(kp[2]) if len(kp) > 2 else 1.0
                if conf >= KEYPOINT_MIN_CONF and (x > 0 or y > 0):
                    flat += [round(x, 2), round(y, 2), 2]
                else:
                    flat += [0, 0, 0]
            p["keypoints"] = flat
            p["num_keypoints"] = int(len(kp_data[i]))

        predictions.append(p)

    return predictions


class YoloService:

    def __init__(self, directory, device="auto", cache_size=3):
        self.directory = directory
        self.device = device
        self.cache_size = cache_size
        self._models = OrderedDict()   # name -> (mtime, YOLO)
        self._load_lock = threading.Lock()
        self._predict_lock = threading.Lock()
        self._error = None

    # ------------------------------------------------------------ discovery
    @property
    def installed(self):
        try:
            import ultralytics  # noqa: F401
            return True
        except ImportError:
            return False

    def model_names(self):
        """Relative paths of all ``.pt`` files in the models folder."""
        if not os.path.isdir(self.directory):
            return []
        names = []
        for root, dirs, files in os.walk(self.directory):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                # SAM 2 checkpoints (sam2*.pt) live here too but are not YOLO models
                if f.lower().endswith('.pt') and not f.startswith('.') and not f.lower().startswith('sam2'):
                    full = os.path.join(root, f)
                    names.append(os.path.relpath(full, self.directory))
        return sorted(names)

    def path_for(self, name):
        """Absolute path of a model, refusing anything outside the folder."""
        if not name or not name.lower().endswith('.pt'):
            raise ValueError("Unknown model")
        base = os.path.realpath(self.directory)
        path = os.path.realpath(os.path.join(base, name))
        if os.path.commonpath([base, path]) != base or not os.path.isfile(path):
            raise ValueError("Unknown model")
        return path

    # ------------------------------------------------------------ loading
    def _resolve_device(self):
        if self.device != "auto":
            return self.device
        try:
            import torch
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def load(self, name):
        path = self.path_for(name)
        mtime = os.path.getmtime(path)
        with self._load_lock:
            cached = self._models.get(name)
            if cached and cached[0] == mtime:
                self._models.move_to_end(name)
                return cached[1]

            from ultralytics import YOLO
            logger.info(f"Loading YOLO model {name}")
            model = YOLO(path)
            self._models[name] = (mtime, model)
            self._models.move_to_end(name)
            while len(self._models) > self.cache_size:
                self._models.popitem(last=False)
            return model

    def info(self, name):
        model = self.load(name)
        names = {int(k): str(v) for k, v in dict(model.names).items()}
        kpt_shape = None
        try:
            kpt_shape = list(model.model.yaml.get("kpt_shape") or []) or None
        except Exception:
            pass
        return {
            "name": name,
            "task": model.task,
            "classes": [names[k] for k in sorted(names)],
            "kpt_shape": kpt_shape,
        }

    def list(self):
        models = []
        for name in self.model_names():
            entry = {"name": name}
            try:
                entry.update(self.info(name))
            except Exception as e:
                logger.warning(f"Could not load model {name}: {e}")
                entry["error"] = str(e)
            models.append(entry)
        return models

    def status(self):
        return {
            "installed": self.installed,
            "directory": self.directory,
            "count": len(self.model_names()) if self.installed else 0,
        }

    # ------------------------------------------------------------ manage
    def save_upload(self, file_storage, overwrite=False):
        """Store an uploaded .pt file and check that it loads.

        Returns the model info. Raises ValueError (bad name/file) or
        FileExistsError (name taken and not ``overwrite``).
        """
        from werkzeug.utils import secure_filename

        name = secure_filename(file_storage.filename or "")
        if not name.lower().endswith('.pt') or name.lower() == '.pt':
            raise ValueError("Only .pt files can be uploaded")

        os.makedirs(self.directory, exist_ok=True)
        path = os.path.join(self.directory, name)
        if os.path.exists(path) and not overwrite:
            raise FileExistsError(name)

        # hidden (not listed) but still a .pt file, so ultralytics loads it now
        tmp = os.path.join(self.directory, f".uploading-{os.getpid()}-{threading.get_ident()}-{name}")
        file_storage.save(tmp)
        try:
            from ultralytics import YOLO
            model = YOLO(tmp)
            dict(model.names)  # make sure the weights really loaded
            if model.task not in ("detect", "obb", "segment", "pose"):
                raise ValueError(f"Unsupported model type: {model.task}")
        except ValueError:
            os.remove(tmp)
            raise
        except Exception as e:
            os.remove(tmp)
            raise ValueError(f"Not a YOLO model that can be loaded: {e}")

        os.replace(tmp, path)
        with self._load_lock:
            self._models.pop(name, None)
        return self.info(name)

    def delete(self, name):
        path = self.path_for(name)
        os.remove(path)
        with self._load_lock:
            self._models.pop(name, None)

    # ------------------------------------------------------------ predict
    def predict(self, name, image_path, conf=0.25, iou=0.7, imgsz=None):
        model = self.load(name)
        names = {int(k): str(v) for k, v in dict(model.names).items()}
        kwargs = {"conf": float(conf), "iou": float(iou), "verbose": False,
                  "device": self._resolve_device()}
        if imgsz:
            kwargs["imgsz"] = int(imgsz)
        with self._predict_lock:
            result = model.predict(image_path, **kwargs)[0]
        return result_to_predictions(result, names)


yolo = YoloService(
    Config.MODELS_DIRECTORY,
    device=Config.YOLO_DEVICE,
)
