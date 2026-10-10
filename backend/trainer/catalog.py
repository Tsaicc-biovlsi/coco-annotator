"""What the installed Ultralytics can train: model names (.pt pretrained
weights it can download, .yaml architectures to train from scratch) by
family and task, and the training arguments with their defaults. The
trainer publishes this, so the page offers exactly what it can run."""
import os
import re

# task of a model name (suffix); names with other suffixes are not offered
_SUFFIX_TASK = {"seg": "segment", "pose": "pose", "obb": "obb", "cls": "classify"}
# not trainable here (other model kinds, special datasets / inputs)
_SKIP = re.compile(r"sam|world|yoloe|nas|distill|depth|objv1|ade20k|grayscale|-sem\b|-sem\.|-sem-|semantic")

FAMILIES = [
    # key, label, name pattern
    ("yolo26", "YOLO26", r"^yolo26"),
    ("yolo12", "YOLO12", r"^yolo12"),
    ("yolo11", "YOLO11", r"^yolo11"),
    ("yolov10", "YOLOv10", r"^yolov10"),
    ("yolov9", "YOLOv9", r"^yolov9"),
    ("yolov8", "YOLOv8", r"^yolov8"),
    ("yolov6", "YOLOv6", r"^yolov6"),
    ("yolov5", "YOLOv5u", r"^yolov5"),
    ("yolov3", "YOLOv3u", r"^yolov3"),
    ("rtdetr", "RT-DETR", r"^rtdetr"),
]

#: training arguments the page may not set (the trainer sets them, or they
#: would point outside the run)
BLOCKED_ARGS = {"task", "mode", "model", "data", "project", "name", "exist_ok", "resume", "cfg",
                "source", "tracker", "distill_model", "save_dir", "format"}
#: arguments that are not about training (prediction / export / tracking)
_NOT_TRAINING = {"vid_stride", "stream_buffer", "visualize", "augment", "agnostic_nms", "classes",
                 "retina_masks", "embed", "show", "save_frames", "save_txt", "save_conf", "save_crop",
                 "show_labels", "show_conf", "show_boxes", "line_width", "optimize", "dynamic",
                 "simplify", "opset", "workspace", "dnn", "quantize", "conf", "nms"}


def task_of(name):
    stem = os.path.splitext(os.path.basename(name))[0].lower()
    for part in reversed(stem.split("-")[1:]):
        if part in _SUFFIX_TASK:
            return _SUFFIX_TASK[part]
    return "detect"


def _family(name):
    for key, label, pattern in FAMILIES:
        if re.match(pattern, name):
            return key
    return None


def _scale_of(name, family):
    stem = os.path.splitext(name)[0]
    rest = stem[len(re.match(dict((k, p) for k, _, p in FAMILIES)[family], stem).group(0)):]
    m = re.match(r"([a-z]\d?)(u)?(?:-|$)", rest) if rest else None
    return m.group(1) if m else ""


def _yaml_names(root):
    """Model yaml names Ultralytics accepts: each file, and for files with
    a "scales" section also <base><scale>.yaml (e.g. yolo26n.yaml)."""
    import yaml
    out = []
    for folder, _, files in os.walk(root):
        for f in sorted(files):
            if not f.endswith(".yaml"):
                continue
            try:
                with open(os.path.join(folder, f)) as fp:
                    scales = (yaml.safe_load(fp) or {}).get("scales") or {}
            except Exception:
                scales = {}
            stem = f[:-5]
            # only an unscaled file (yolo26.yaml, yolov8-p2.yaml), not yolov10n.yaml
            m = re.match(r"^(yolov?\d+)((?:-.*)?)$", stem)
            if scales and m:
                out += [f"{m.group(1)}{s}{m.group(2)}.yaml" for s in scales]
            else:
                out.append(f)
    return out


def build():
    try:
        import ultralytics
        from ultralytics.cfg import DEFAULT_CFG_DICT
        from ultralytics.utils.downloads import GITHUB_ASSETS_NAMES
    except ImportError:
        return {"families": [], "args": {}, "version": None}
    names = [n for n in GITHUB_ASSETS_NAMES if n.endswith(".pt")]
    names += _yaml_names(os.path.join(os.path.dirname(ultralytics.__file__), "cfg", "models"))
    fams = {key: {"key": key, "label": label, "items": []} for key, label, _ in FAMILIES}
    seen = set()
    for name in sorted(set(names)):
        if _SKIP.search(name) or name in seen:
            continue
        family = _family(name)
        if family is None:
            continue
        seen.add(name)
        fams[family]["items"].append({
            "name": name, "kind": "pt" if name.endswith(".pt") else "yaml",
            "task": task_of(name), "scale": _scale_of(name, family),
        })
    args = {k: v for k, v in DEFAULT_CFG_DICT.items() if k not in BLOCKED_ARGS and k not in _NOT_TRAINING}
    return {"families": [f for f in fams.values() if f["items"]], "args": args,
            "version": getattr(ultralytics, "__version__", None)}


def names(catalog):
    return {i["name"]: i for f in (catalog or {}).get("families", []) for i in f["items"]}
