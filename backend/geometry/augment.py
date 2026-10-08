"""Data augmentation for exports.

Each chosen image gets ``copies`` new versions; every version applies a
random subset of the chosen operations to the picture *and* to its
annotations (polygons, boxes, rotated boxes, keypoints), so all export
formats can write them like ordinary images.

Options (``parse_options``)::

    {"copies": 2,
     "ops": {"hflip": true, "vflip": false, "rot90": false,
             "rotate": 15,          # degrees (0 / false: off)
             "scale": 0.7,          # smallest zoom crop (0 / false: off)
             "color": true, "blur": false, "noise": false}}
"""
import math
import os
import random

import numpy as np

from . import polygon_to_rbbox, rbbox_to_polygon

GEOMETRIC = ("scale", "rotate", "rot90", "hflip", "vflip")
PHOTOMETRIC = ("color", "blur", "noise")
OPS = GEOMETRIC + PHOTOMETRIC
MAX_COPIES = 5

# a shape that keeps less than this share of its area inside the picture is dropped
MIN_VISIBLE = 0.25


def parse_options(raw):
    """Clean options, or None when augmentation is off / nothing is chosen."""
    if not isinstance(raw, dict):
        return None
    try:
        copies = int(raw.get("copies") or 0)
    except (TypeError, ValueError):
        return None
    ops_in = raw.get("ops") if isinstance(raw.get("ops"), dict) else {}
    ops = {}
    for name in ("hflip", "vflip", "rot90", "color", "blur", "noise"):
        if ops_in.get(name) is True:
            ops[name] = True
    try:
        rotate = float(ops_in.get("rotate") or 0)
    except (TypeError, ValueError):
        rotate = 0
    if rotate:
        ops["rotate"] = min(max(abs(rotate), 1.0), 45.0)
    try:
        scale = float(ops_in.get("scale") or 0)
    except (TypeError, ValueError):
        scale = 0
    if scale:
        ops["scale"] = min(max(scale, 0.5), 0.95)
    if copies < 1 or not ops:
        return None
    return {"copies": min(copies, MAX_COPIES), "ops": ops}


# ---- keypoints: left <-> right on a horizontal flip --------------------------

def _swapped(name):
    lower = name.lower()
    for a, b in (("left", "right"), ("左", "右")):
        if a in lower or b in lower:
            return lower.replace(a, "\0").replace(b, a).replace("\0", b)
    return lower


def flip_map(labels):
    """Index of each keypoint's mirror partner (itself when it has none)."""
    lookup = {name.lower(): i for i, name in enumerate(labels or [])}
    return [lookup.get(_swapped(name), i) for i, name in enumerate(labels or [])]


# ---- geometry of one annotation while it is being transformed ---------------

class _Shape:
    def __init__(self, ann):
        self.ann = ann
        self.polys = []
        for ring in ann.get("segmentation") or []:
            if isinstance(ring, list) and len(ring) >= 6:
                self.polys.append(np.asarray(ring, dtype=np.float64).reshape(-1, 2))
        kps = ann.get("keypoints") or []
        self.kps = np.asarray(kps, dtype=np.float64).reshape(-1, 3) if len(kps) >= 3 else None
        self.isbbox = bool(ann.get("isbbox"))
        self.isrbbox = bool(ann.get("isrbbox")) and len(self.polys) == 1 and len(self.polys[0]) == 4

    def apply(self, fn):
        """fn: (N, 2) points -> (N, 2) points"""
        self.polys = [fn(p) for p in self.polys]
        if self.kps is not None:
            visible = self.kps[:, 2] > 0
            if visible.any():
                self.kps[visible, :2] = fn(self.kps[visible, :2])


def _affine(points, m):
    return points @ m[:, :2].T + m[:, 2]


# ---- the operations: (image, shapes, rng) -> image ---------------------------

def _hflip(img, shapes, rng, opt, flips):
    w = img.shape[1]
    for s in shapes:
        s.apply(lambda p: np.column_stack([w - p[:, 0], p[:, 1]]))
        partner = flips.get(s.ann.get("category_id"))
        if s.kps is not None and partner and len(partner) == len(s.kps):
            s.kps = s.kps[partner]
    return img[:, ::-1].copy()


def _vflip(img, shapes, rng, opt, flips):
    h = img.shape[0]
    for s in shapes:
        s.apply(lambda p: np.column_stack([p[:, 0], h - p[:, 1]]))
    return img[::-1].copy()


def _rot90(img, shapes, rng, opt, flips):
    import cv2
    for _ in range(rng.choice((1, 2, 3))):
        h = img.shape[0]
        # clockwise: (x, y) -> (h - y, x)
        for s in shapes:
            s.apply(lambda p, h=h: np.column_stack([h - p[:, 1], p[:, 0]]))
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    return img


def _rotate(img, shapes, rng, opt, flips):
    """A small rotation; the canvas grows so nothing is cut off."""
    import cv2
    h, w = img.shape[:2]
    angle = rng.uniform(-opt, opt)
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(round(h * sin + w * cos)), int(round(h * cos + w * sin))
    m[0, 2] += nw / 2.0 - w / 2.0
    m[1, 2] += nh / 2.0 - h / 2.0
    for s in shapes:
        s.apply(lambda p: _affine(p, m))
    return cv2.warpAffine(img, m, (nw, nh), flags=cv2.INTER_LINEAR, borderValue=(114, 114, 114))


def _scale(img, shapes, rng, opt, flips):
    """Zoom in: crop a part (at least ``opt`` of each side) back to full size."""
    import cv2
    h, w = img.shape[:2]
    s = rng.uniform(opt, 1.0)
    cw, ch = max(1, int(w * s)), max(1, int(h * s))
    x0, y0 = rng.randint(0, w - cw), rng.randint(0, h - ch)
    sx, sy = w / cw, h / ch
    for shape in shapes:
        shape.apply(lambda p: np.column_stack([(p[:, 0] - x0) * sx, (p[:, 1] - y0) * sy]))
    return cv2.resize(img[y0:y0 + ch, x0:x0 + cw], (w, h), interpolation=cv2.INTER_LINEAR)


def _color(img, shapes, rng, opt, flips):
    import cv2
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 0] = (hsv[..., 0] + rng.uniform(-5, 5)) % 180
    hsv[..., 1] *= rng.uniform(0.7, 1.3)
    hsv[..., 2] *= rng.uniform(0.75, 1.25)
    out = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    contrast = rng.uniform(0.8, 1.2)
    out = (out - out.mean()) * contrast + out.mean()
    return np.clip(out, 0, 255).astype(np.uint8)


def _blur(img, shapes, rng, opt, flips):
    import cv2
    k = rng.choice((3, 5))
    return cv2.GaussianBlur(img, (k, k), 0)


def _noise(img, shapes, rng, opt, flips):
    sigma = rng.uniform(4, 10)
    noise = np.random.default_rng(rng.randint(0, 2 ** 31)).normal(0, sigma, img.shape)
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)


_FUNCS = {"hflip": _hflip, "vflip": _vflip, "rot90": _rot90, "rotate": _rotate, "scale": _scale,
          "color": _color, "blur": _blur, "noise": _noise}


def pick_ops(ops, rng):
    """Each chosen operation with a 50 % chance (at least one), in a fixed order."""
    names = [n for n in OPS if n in ops]
    chosen = [n for n in names if rng.random() < 0.5]
    if not chosen:
        chosen = [rng.choice(names)]
    return chosen


# ---- shapes back to COCO -----------------------------------------------------

def _finish(shape, w, h):
    """The transformed annotation (a new dict), or None when it left the picture."""
    from shapely.geometry import Polygon, box
    from shapely.validation import make_valid

    ann = dict(shape.ann)
    frame = box(0, 0, w, h)
    rings, area, before = [], 0.0, 0.0
    for pts in shape.polys:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = make_valid(poly)
        before += poly.area
        inside = poly.intersection(frame)
        for part in getattr(inside, "geoms", [inside]):
            if part.geom_type == "Polygon" and part.area >= 1.0:
                coords = np.asarray(part.exterior.coords)[:-1]
                rings.append([round(float(v), 2) for v in coords.reshape(-1)])
                area += part.area

    kps = None
    if shape.kps is not None:
        kps = shape.kps.copy()
        outside = (kps[:, 0] < 0) | (kps[:, 1] < 0) | (kps[:, 0] > w) | (kps[:, 1] > h)
        kps[outside & (kps[:, 2] > 0)] = 0
        ann["keypoints"] = [round(float(v), 2) if i % 3 != 2 else int(v) for i, v in enumerate(kps.reshape(-1))]
        ann["num_keypoints"] = int((kps[:, 2] > 0).sum())

    if shape.polys:
        if not rings or area < 4.0 or (before > 0 and area / before < MIN_VISIBLE):
            return None
        xs = [x for r in rings for x in r[0::2]]
        ys = [y for r in rings for y in r[1::2]]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        if shape.isrbbox:
            whole = before > 0 and abs(area - before) / before < 0.01
            # fully inside: keep the corner order (the box's orientation)
            corners = shape.polys[0].reshape(-1) if whole else np.asarray(rings[0])
            rbbox = [round(float(v), 3) for v in polygon_to_rbbox(corners)]
            ann["rbbox"] = rbbox
            ann["segmentation"] = [rbbox_to_polygon(rbbox)]
            ann["area"] = round(rbbox[2] * rbbox[3], 2)
        elif shape.isbbox:
            ann["segmentation"] = [[x0, y0, x1, y0, x1, y1, x0, y1]]
            ann["area"] = round((x1 - x0) * (y1 - y0), 2)
        else:
            ann["segmentation"] = rings
            ann["area"] = round(area, 2)
        ann["bbox"] = [round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2)]
    elif kps is not None:
        visible = kps[kps[:, 2] > 0]
        if not len(visible):
            return None
        x0, y0 = visible[:, 0].min(), visible[:, 1].min()
        x1, y1 = visible[:, 0].max(), visible[:, 1].max()
        ann["bbox"] = [round(float(x0), 2), round(float(y0), 2), round(float(x1 - x0), 2), round(float(y1 - y0), 2)]
    else:
        return None
    return ann


def augment_image(img, annotations, ops, rng, flips):
    """One augmented version: (image, [annotation dicts], [operations used])."""
    shapes = [_Shape(a) for a in annotations]
    used = pick_ops(ops, rng)
    for name in used:
        img = _FUNCS[name](img, shapes, rng, ops[name], flips)
    h, w = img.shape[:2]
    out = [a for a in (_finish(s, w, h) for s in shapes) if a is not None]
    return img, out, used


def augment_coco(coco, images, options, seed, out_dir, log=None):
    """Augmented copies of ``images`` (COCO image dicts with a ``path``).

    Returns (new images, new annotations, {new image id: original id}).
    The pictures are written as JPEG into ``out_dir``.
    """
    import cv2

    os.makedirs(out_dir, exist_ok=True)
    rng = random.Random(seed)
    flips = {c["id"]: flip_map(c.get("keypoints") or c.get("keypoint_labels") or [])
             for c in coco.get("categories", [])}
    by_image = {}
    for a in coco.get("annotations", []):
        by_image.setdefault(a.get("image_id"), []).append(a)
    next_image = max([i["id"] for i in coco.get("images", [])] + [0]) + 1
    next_ann = max([a.get("id", 0) for a in coco.get("annotations", [])] + [0]) + 1

    new_images, new_annotations, source = [], [], {}
    for n, image in enumerate(images):
        path = image.get("path")
        picture = cv2.imread(path, cv2.IMREAD_COLOR) if path and os.path.isfile(path) else None
        if picture is None:
            if log:
                log(f"Image file missing, not augmented: {image.get('file_name')}")
            continue
        stem = os.path.splitext(os.path.basename(image.get("file_name") or f"image{image['id']}"))[0]
        for k in range(1, options["copies"] + 1):
            pic, anns, used = augment_image(picture, by_image.get(image["id"], []), options["ops"], rng, flips)
            name = f"{stem}_aug{k}.jpg"
            file = os.path.join(out_dir, f"{image['id']}_{k}.jpg")
            cv2.imwrite(file, pic, [cv2.IMWRITE_JPEG_QUALITY, 95])
            h, w = pic.shape[:2]
            new = dict(image, id=next_image, file_name=name, path=file, width=w, height=h,
                       augmented_from=image["id"], augment_ops=used)
            new_images.append(new)
            source[next_image] = image["id"]
            for a in anns:
                new_annotations.append(dict(a, id=next_ann, image_id=next_image))
                next_ann += 1
            next_image += 1
        if log and (n + 1) % 50 == 0:
            log(f"Augmented {n + 1} / {len(images)} images")
    return new_images, new_annotations, source
