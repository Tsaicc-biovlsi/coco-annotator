
from database import (
    fix_ids,
    ImageModel,
    CategoryModel,
    AnnotationModel,
    DatasetModel,
    TaskModel,
    ExportModel
)

# import pycocotools.mask as mask
import numpy as np
import time
import json
import os

from celery import shared_task
from geometry import rbbox_to_polygon, rbbox_area
from ..socket import create_socket
from mongoengine import Q


@shared_task
def export_annotations(task_id, dataset_id, categories, with_empty_images=False,
                       fmt="coco", yolo_task="detect", with_images=False, split=None, seed=42):

    task = TaskModel.objects.get(id=task_id)
    dataset = DatasetModel.objects.get(id=dataset_id)

    task.update(status="PROGRESS")
    socket = create_socket()

    task.info(f"Beginning Export ({'YOLO ' + yolo_task if fmt == 'yolo' else 'COCO'} Format)")

    db_categories = CategoryModel.objects(id__in=categories, deleted=False) \
        .only(*CategoryModel.COCO_PROPERTIES)
    db_images = ImageModel.objects(
        deleted=False, dataset_id=dataset.id).only(
        *ImageModel.COCO_PROPERTIES)
    db_annotations = AnnotationModel.objects(
        deleted=False, category_id__in=categories)

    total_items = db_categories.count()

    coco = {
        'images': [],
        'categories': [],
        'annotations': []
    }

    total_items += db_images.count()
    progress = 0

    # iterate though all categoires and upsert
    category_names = []
    # keep the order that was asked for (it becomes the YOLO class index)
    position = {c: i for i, c in enumerate(categories)}
    for category in sorted(fix_ids(db_categories), key=lambda c: position.get(c.get('id'), len(position))):

        if len(category.get('keypoint_labels', [])) > 0:
            category['keypoints'] = category.pop('keypoint_labels', [])
            category['skeleton'] = category.pop('keypoint_edges', [])
        else:
            if 'keypoint_edges' in category:
                del category['keypoint_edges']
            if 'keypoint_labels' in category:
                del category['keypoint_labels']

        task.info(f"Adding category: {category.get('name')}")
        coco.get('categories').append(category)
        category_names.append(category.get('name'))

        progress += 1
        task.set_progress((progress / total_items) * 100, socket=socket)

    total_annotations = db_annotations.count()
    total_images = db_images.count()
    for image in db_images:
        image = fix_ids(image)

        progress += 1
        task.set_progress((progress / total_items) * 100, socket=socket)

        annotations = db_annotations.filter(image_id=image.get('id'))\
            .only(*AnnotationModel.COCO_PROPERTIES)
        annotations = fix_ids(annotations)

        if len(annotations) == 0:
            if with_empty_images:
                coco.get('images').append(image)
            continue

        num_annotations = 0
        for annotation in annotations:

            has_keypoints = len(annotation.get('keypoints', [])) > 0
            has_segmentation = len(annotation.get('segmentation', [])) > 0

            if has_keypoints or has_segmentation:

                if not has_keypoints:
                    if 'keypoints' in annotation:
                        del annotation['keypoints']
                else:
                    arr = np.array(annotation.get('keypoints', []))
                    arr = arr[2::3]
                    annotation['num_keypoints'] = len(arr[arr > 0])

                if not annotation.get('isrbbox'):
                    annotation.pop('isrbbox', None)
                    annotation.pop('rbbox', None)

                num_annotations += 1
                coco.get('annotations').append(annotation)

        task.info(
            f"Exporting {num_annotations} annotations for image {image.get('id')}")
        coco.get('images').append(image)

    task.info(
        f"Done export {total_annotations} annotations and {total_images} images from {dataset.name}")

    timestamp = time.time()
    directory = f"{dataset.directory}.exports/"
    if not os.path.exists(directory):
        os.makedirs(directory)

    subsets = None
    if split:
        from geometry.yolo_format import split_images
        subsets = split_images([img['id'] for img in coco['images']], split, seed)
        split_counts = {name: sum(1 for v in subsets.values() if v == name) for name in ("train", "val", "test")}
        task.info("Split (seed {}): {}".format(
            seed, ", ".join(f"{k} {split[k]}% = {split_counts[k]} images" for k in split_counts)))

    if fmt == "yolo":
        file_path = f"{directory}yolo-{yolo_task}-{timestamp}.zip"
        task.info(f"Writing YOLO {yolo_task} labels to {file_path}")
        from geometry.yolo_format import safe_prefix
        # YOLO files are always named <dataset>_<image> (unique across datasets)
        prefix = safe_prefix(dataset.name)
        if prefix:
            task.info(f"File names start with the dataset name: {prefix}<image name>")
        result = _write_yolo_zip(coco, yolo_task, with_images, file_path, task, subsets, split, prefix)
        tags = ["YOLO", yolo_task, *category_names]
        task.info(f"Wrote {result['written']} labels ({result['skipped']} annotations "
                  f"could not be converted to {yolo_task})")
    elif subsets:
        file_path = f"{directory}coco-split-{timestamp}.zip"
        task.info(f"Writing COCO train / val / test files to {file_path}")
        _write_coco_split_zip(coco, subsets, file_path)
        tags = ["COCO", *category_names]
    else:
        file_path = f"{directory}coco-{timestamp}.json"
        task.info(f"Writing export to file {file_path}")
        with open(file_path, 'w') as fp:
            json.dump(coco, fp)
        tags = ["COCO", *category_names]

    task.info("Creating export object")
    export = ExportModel(dataset_id=dataset.id, path=file_path, tags=tags)
    if fmt == "yolo":
        export.prefix_dataset = True
    if subsets:
        export.split = split
        export.split_counts = split_counts
        export.seed = seed
    export.save()

    task.set_progress(100, socket=socket)


def _write_coco_split_zip(coco, subsets, file_path):
    """One COCO json per subset (train.json, val.json, test.json) in a zip."""
    import zipfile
    tmp_path = file_path + ".tmp"
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ("train", "val", "test"):
            images = [img for img in coco["images"] if subsets.get(img["id"]) == name]
            if not images:
                continue
            ids = {img["id"] for img in images}
            part = dict(coco, images=images,
                        annotations=[a for a in coco["annotations"] if a.get("image_id") in ids])
            zf.writestr(f"{name}.json", json.dumps(part))
    os.replace(tmp_path, file_path)


def _write_yolo_zip(coco, yolo_task, with_images, file_path, task, subsets=None, split=None, prefix=""):
    """COCO dict -> zip with labels/*.txt, data.yaml, classes.txt (+ images/).
    With ``subsets`` ({image_id: train/val/test}) files go to labels/train/ etc."""
    import zipfile
    from geometry.yolo_format import coco_to_yolo, data_yaml, stem

    result = coco_to_yolo(coco, yolo_task)
    tmp_path = file_path + ".tmp"
    used = set()
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for image in coco["images"]:
            name = prefix + stem(image["file_name"])
            if name in used:  # same name in two folders
                name = f"{name}_{image['id']}"
            used.add(name)
            lines = result["labels"].get(image["id"], [])
            folder = f"/{subsets[image['id']]}" if subsets else ""
            zf.writestr(f"labels{folder}/{name}.txt", "\n".join(lines) + ("\n" if lines else ""))
            if with_images:
                path = image.get("path")
                if path and os.path.isfile(path):
                    ext = os.path.splitext(path)[1]
                    # images are already compressed
                    zf.write(path, f"images{folder}/{name}{ext}", compress_type=zipfile.ZIP_STORED)
                else:
                    task.warning(f"Image file missing: {image.get('file_name')}")
        zf.writestr("data.yaml", data_yaml(result["names"], yolo_task, result["kpt_shape"], result["flip_idx"],
                                           split=split if subsets else None))
        zf.writestr("classes.txt", "\n".join(result["names"]) + "\n")
    os.replace(tmp_path, file_path)
    return result


def _polygon_area(flat):
    pts = np.asarray(flat, dtype=float).reshape(-1, 2)
    x, y = pts[:, 0], pts[:, 1]
    return float(abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) / 2)


def _rle_to_polygons(rle):
    """COCO RLE (compressed or not) -> polygon list ([] if it cannot be read)."""
    try:
        from pycocotools import mask as mask_util
        import cv2
        if isinstance(rle.get('counts'), list):
            h, w = rle['size']
            rle = mask_util.frPyObjects(rle, h, w)
        mask = mask_util.decode(rle).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return [c.reshape(-1).astype(float).tolist() for c in contours
                if len(c) >= 3 and cv2.contourArea(c) > 0]
    except Exception:
        return []


@shared_task
def import_annotations(task_id, dataset_id, coco_json):

    task = TaskModel.objects.get(id=task_id)
    dataset = DatasetModel.objects.get(id=dataset_id)

    task.update(status="PROGRESS")
    socket = create_socket()

    task.info("Beginning Import")

    images = ImageModel.objects(dataset_id=dataset.id, deleted=False)
    categories = CategoryModel.objects

    coco_images = coco_json.get('images', [])
    coco_annotations = coco_json.get('annotations', [])
    coco_categories = coco_json.get('categories', [])

    task.info(f"Importing {len(coco_categories)} categories, "
              f"{len(coco_images)} images, and "
              f"{len(coco_annotations)} annotations")

    total_items = sum([
        len(coco_categories),
        len(coco_annotations),
        len(coco_images)
    ])
    progress = 0

    task.info("===== Importing Categories =====")
    # category id mapping  ( file : database )
    categories_id = {}

    # Create any missing categories
    for category in coco_categories:

        category_name = category.get('name')
        category_id = category.get('id')
        category_model = categories.filter(name__iexact=category_name).first()

        if category_model is None:
            # expected when importing new classes, not a problem
            task.info(f"{category_name} category not found (creating a new one)")

            new_category = CategoryModel(
                name=category_name,
                keypoint_edges=category.get('skeleton', []),
                keypoint_labels=category.get('keypoints', [])
            )
            new_category.save()

            category_model = new_category
            dataset.categories.append(new_category.id)

        elif category_model.id not in dataset.categories:
            # the category exists (e.g. used by another dataset): add it here
            dataset.categories.append(category_model.id)

        if category.get('keypoints') and not category_model.keypoint_labels:
            # e.g. a YOLO pose import into a category without keypoints yet
            category_model.update(keypoint_labels=category.get('keypoints'),
                                  keypoint_edges=category.get('skeleton', []))

        task.info(f"{category_name} category found")
        # map category ids
        categories_id[category_id] = category_model.id

        # update progress
        progress += 1
        task.set_progress((progress / total_items) * 100, socket=socket)

    dataset.update(set__categories=dataset.categories)

    task.info("===== Loading Images =====")
    # image id mapping ( file: database )
    images_id = {}
    categories_by_image = {}

    # Find all images
    for image in coco_images:
        image_id = image.get('id')
        image_filename = image.get('file_name')

        # update progress
        progress += 1
        task.set_progress((progress / total_items) * 100, socket=socket)

        image_model = images.filter(file_name__exact=image_filename).all()
        if len(image_model) == 0 and image_filename:
            # exports often keep a folder in file_name ("images/train/a.jpg")
            base = os.path.basename(str(image_filename).replace("\\", "/"))
            if base != image_filename:
                image_model = images.filter(file_name__exact=base).all()

        if len(image_model) == 0:
            task.warning(f"Could not find image {image_filename}")
            continue

        if len(image_model) > 1:
            task.error(
                f"Too many images found with the same file name: {image_filename}")
            continue

        task.info(f"Image {image_filename} found")
        image_model = image_model[0]
        images_id[image_id] = image_model
        categories_by_image[image_id] = list()

    task.info("===== Import Annotations =====")
    for annotation in coco_annotations:

        image_id = annotation.get('image_id')
        category_id = annotation.get('category_id')
        segmentation = annotation.get('segmentation', [])
        keypoints = annotation.get('keypoints', [])
        # is_crowd = annotation.get('iscrowed', False)
        area = annotation.get('area', 0)
        bbox = annotation.get('bbox', [0, 0, 0, 0])
        isbbox = annotation.get('isbbox', False)
        rbbox = annotation.get('rbbox') or []
        isrbbox = len(rbbox) == 5

        # Rotated boxes may come without a polygon (e.g. converted from DOTA)
        if isrbbox and not segmentation:
            segmentation = [rbbox_to_polygon(rbbox)]
            area = rbbox_area(rbbox)
            xs, ys = segmentation[0][0::2], segmentation[0][1::2]
            bbox = [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]

        progress += 1
        task.set_progress((progress / total_items) * 100, socket=socket)

        # RLE masks (crowd annotations) become polygons
        if isinstance(segmentation, dict):
            segmentation = _rle_to_polygons(segmentation)
            if segmentation:
                area = sum(_polygon_area(p) for p in segmentation)

        # box-only annotations (many detectors and converters export these)
        if not segmentation and not keypoints and len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0:
            x, y, w, h = [float(v) for v in bbox]
            segmentation = [[x, y, x + w, y, x + w, y + h, x, y + h]]
            area = area or w * h
            isbbox = True

        has_segmentation = len(segmentation) > 0
        has_keypoints = len(keypoints) > 0
        if not has_segmentation and not has_keypoints:
            task.warning(
                f"Annotation {annotation.get('id')} has no segmentation or keypoints")
            continue

        try:
            image_model = images_id[image_id]
            category_model_id = categories_id[category_id]
            image_categories = categories_by_image[image_id]
        except KeyError:
            task.warning(
                f"Could not find image assoicated with annotation {annotation.get('id')}")
            continue

        annotation_model = AnnotationModel.objects(
            image_id=image_model.id,
            category_id=category_model_id,
            segmentation=segmentation,
            keypoints=keypoints
        ).first()

        if annotation_model is None:
            task.info(f"Creating annotation data ({image_id}, {category_id})")

            annotation_model = AnnotationModel(image_id=image_model.id)
            annotation_model.category_id = category_model_id

            annotation_model.color = annotation.get('color')
            annotation_model.metadata = annotation.get('metadata', {})

            if has_segmentation:
                annotation_model.segmentation = segmentation
                annotation_model.area = area
                annotation_model.bbox = bbox

            if has_keypoints:
                annotation_model.keypoints = keypoints

            annotation_model.isbbox = isbbox
            if isrbbox:
                annotation_model.isrbbox = True
                annotation_model.rbbox = rbbox
            annotation_model.save()

            image_categories.append(category_model_id)
        else:
            annotation_model.update(deleted=False, isbbox=isbbox)
            image_categories.append(category_model_id)
            task.info(
                f"Annotation already exists (i:{image_id}, c:{category_id})")

    for image_id in images_id:
        image_model = images_id[image_id]
        category_ids = categories_by_image[image_id]
        all_category_ids = list(image_model.category_ids)
        all_category_ids += category_ids

        # image_id is the id in the COCO file; count by the database id
        num_annotations = AnnotationModel.objects(
            Q(image_id=image_model.id) & Q(deleted=False) &
            (Q(area__gt=0) | Q(keypoints__0__exists=True))
        ).count()

        image_model.update(
            set__annotated=True,
            set__category_ids=list(set(all_category_ids)),
            set__num_annotations=num_annotations,
            set__regenerate_thumbnail=True
        )

    task.set_progress(100, socket=socket)


__all__ = ["export_annotations", "import_annotations"]
