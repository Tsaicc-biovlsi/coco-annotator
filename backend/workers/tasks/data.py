
from database import (
    fix_ids,
    ImageModel,
    CategoryModel,
    AnnotationModel,
    DatasetModel,
    TaskModel,
    ExportModel,
    ActivityModel
)

# import pycocotools.mask as mask
import numpy as np
import time
import datetime
import json
import os

from celery import shared_task
from geometry import rbbox_to_polygon, rbbox_area
from ..socket import create_socket
from mongoengine import Q


@shared_task
def export_annotations(task_id, dataset_id, categories, with_empty_images=False,
                       fmt="coco", yolo_task="detect", with_images=False, split=None, seed=42,
                       folder=None, only_approved=False):

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
    if only_approved:
        db_images = db_images.filter(status='approved')
        task.info(f"Only approved images: {db_images.count()}")
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

    # classify: images with a whole-image class are exported even without annotations
    explicit = {}
    if fmt == "yolo" and yolo_task == "classify":
        explicit = {row['_id']: row['image_class'] for row in ImageModel.objects(
            dataset_id=dataset.id, deleted=False, image_class__ne=None, image_class__in=categories)
            .only('id', 'image_class').as_pymongo()}

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
            if with_empty_images or image.get('id') in explicit:
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

    classes = None
    if fmt == "yolo" and yolo_task == "classify":
        # one class per image: the whole-image class, else its annotations
        from geometry.yolo_format import image_classes
        classes, mixed, empty = image_classes(coco, explicit)
        task.info(f"{sum(1 for i in classes if i in explicit)} images use their whole-image class")
        if mixed:
            task.warning(f"{len(mixed)} images have annotations of several categories and are skipped "
                         "(classification needs one class per image): "
                         + ", ".join(img['file_name'] for img in mixed[:10]))
        if empty:
            task.info(f"{len(empty)} images without annotations are skipped")
        coco['images'] = [img for img in coco['images'] if img['id'] in classes]

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
        from geometry.yolo_format import safe_folder, safe_prefix
        # YOLO files are always named <dataset>_<image> (unique across datasets)
        prefix = safe_prefix(dataset.name)
        folder = safe_folder(folder, safe_folder(dataset.name))
        task.info(f"Folder in the zip: {folder}/ (train, val, test)")
        if prefix:
            task.info(f"File names start with the dataset name: {prefix}<image name>")
        if yolo_task == "classify":
            result = _write_classify_zip(coco, classes, file_path, task, subsets, prefix, folder)
            task.info(f"Wrote {result['written']} images into class folders")
        elif yolo_task == "semantic":
            result = _write_semantic_zip(coco, with_images, file_path, task, subsets, split, prefix, folder)
            task.info(f"Wrote {result['written']} masks ({result['skipped']} annotations without a shape skipped)")
        else:
            result = _write_yolo_zip(coco, yolo_task, with_images, file_path, task, subsets, split, prefix, folder)
            task.info(f"Wrote {result['written']} labels ({result['skipped']} annotations "
                      f"could not be converted to {yolo_task})")
        tags = ["YOLO", yolo_task, *category_names]
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
        export.folder = folder
    if only_approved:
        export.only_approved = True
    if subsets:
        export.split = split
        export.split_counts = split_counts
        export.seed = seed
    export.save()
    ActivityModel.objects(task_id=task_id, action='export').update(
        set__counts={'images': len(coco.get('images', [])), 'annotations': len(coco.get('annotations', [])),
                     'categories': len(category_names)},
        set__detail__categories=list(category_names)[:50], set__detail__export_id=export.id,
        set__updated_at=datetime.datetime.utcnow())

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


def _unique_names(coco, prefix):
    """image id -> <prefix><file stem>, made unique (same name in two folders)."""
    from geometry.yolo_format import stem
    names, used = {}, set()
    for image in coco["images"]:
        name = prefix + stem(image["file_name"])
        if name in used:
            name = f"{name}_{image['id']}"
        used.add(name)
        names[image["id"]] = name
    return names


def _add_image(zf, image, arcname_no_ext, task):
    """Copy the image file into the zip (uncompressed: images are already)."""
    import zipfile
    path = image.get("path")
    if path and os.path.isfile(path):
        zf.write(path, arcname_no_ext + os.path.splitext(path)[1], compress_type=zipfile.ZIP_STORED)
        return True
    task.warning(f"Image file missing: {image.get('file_name')}")
    return False


def _write_classify_zip(coco, classes, file_path, task, subsets=None, prefix="", root="dataset"):
    """classify: <root>/<subset>/<class name>/<image> (images only, no labels).
    Without a split: <root>/<class name>/<image>, which Ultralytics splits
    80/20 by itself."""
    import zipfile
    from geometry.yolo_format import safe_folder

    names = [c["name"] for c in coco["categories"]]
    folders, seen = [], set()
    for i, name in enumerate(names):
        folder = safe_folder(name, f"class_{i}")
        if folder in seen:
            folder = f"{folder}_{i}"
        seen.add(folder)
        folders.append(folder)
    file_names = _unique_names(coco, prefix)
    subset_names = sorted(set(subsets.values()), key=("train", "val", "test").index) if subsets else [None]

    written = 0
    tmp_path = file_path + ".tmp"
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # every class folder in every subset, so they all list the same classes
        for subset in subset_names:
            for folder in folders:
                zf.writestr(f"{root}/{subset + '/' if subset else ''}{folder}/", "")
        for image in coco["images"]:
            subset = subsets[image["id"]] if subsets else None
            base = f"{root}/{subset + '/' if subset else ''}{folders[classes[image['id']]]}/{file_names[image['id']]}"
            written += _add_image(zf, image, base, task)
        # Ultralytics numbers classify classes by folder name, alphabetically
        zf.writestr("classes.txt", "\n".join(sorted(folders)) + "\n")
    os.replace(tmp_path, file_path)
    return {"written": written, "skipped": 0, "names": sorted(folders)}


def _write_semantic_zip(coco, with_images, file_path, task, subsets=None, split=None, prefix="", root="dataset"):
    """semantic: <root>/<subset>/masks/<image>.png (+ images/), class 0 is
    background and the categories start at 1."""
    import zipfile
    import cv2
    from geometry.yolo_format import SEMANTIC_BACKGROUND, data_yaml, semantic_mask

    names = [SEMANTIC_BACKGROUND] + [c["name"] for c in coco["categories"]]
    index = {c["id"]: i for i, c in enumerate(coco["categories"])}
    by_image = {}
    for a in coco["annotations"]:
        by_image.setdefault(a.get("image_id"), []).append(a)
    file_names = _unique_names(coco, prefix)
    used_split = None
    if subsets:
        present = set(subsets.values())
        used_split = {k: (v if k in present else 0) for k, v in split.items()}

    written = skipped = 0
    tmp_path = file_path + ".tmp"
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for image in coco["images"]:
            folder = f"{root}/" + (subsets[image["id"]] if subsets else "train")
            annotations = by_image.get(image["id"], [])
            skipped += sum(1 for a in annotations if not a.get("segmentation"))
            ok, png = cv2.imencode(".png", semantic_mask(image, annotations, index))
            zf.writestr(f"{folder}/masks/{file_names[image['id']]}.png", png.tobytes())
            written += 1
            if with_images:
                _add_image(zf, image, f"{folder}/images/{file_names[image['id']]}", task)
        zf.writestr("data.yaml", data_yaml(names, "semantic", split=used_split, root=root, masks_dir="masks"))
        zf.writestr("classes.txt", "\n".join(names) + "\n")
    os.replace(tmp_path, file_path)
    return {"written": written, "skipped": skipped, "names": names}


def _write_yolo_zip(coco, yolo_task, with_images, file_path, task, subsets=None, split=None, prefix="",
                    root="dataset"):
    """COCO dict -> zip with data.yaml, classes.txt and <root>/<subset>/labels/*.txt
    (+ <root>/<subset>/images/). ``subsets`` ({image_id: train/val/test})
    picks the folder; without it everything goes to train/."""
    import zipfile
    from geometry.yolo_format import coco_to_yolo, data_yaml, stem

    result = coco_to_yolo(coco, yolo_task)
    used_split = None
    if subsets:
        # a subset that got no images (tiny datasets) is left out of data.yaml
        present = set(subsets.values())
        used_split = {k: (v if k in present else 0) for k, v in split.items()}
    tmp_path = file_path + ".tmp"
    used = set()
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for image in coco["images"]:
            name = prefix + stem(image["file_name"])
            if name in used:  # same name in two folders
                name = f"{name}_{image['id']}"
            used.add(name)
            lines = result["labels"].get(image["id"], [])
            folder = f"{root}/" + (subsets[image['id']] if subsets else "train")
            zf.writestr(f"{folder}/labels/{name}.txt", "\n".join(lines) + ("\n" if lines else ""))
            if with_images:
                path = image.get("path")
                if path and os.path.isfile(path):
                    ext = os.path.splitext(path)[1]
                    # images are already compressed
                    zf.write(path, f"{folder}/images/{name}{ext}", compress_type=zipfile.ZIP_STORED)
                else:
                    task.warning(f"Image file missing: {image.get('file_name')}")
        zf.writestr("data.yaml", data_yaml(result["names"], yolo_task, result["kpt_shape"], result["flip_idx"],
                                           split=used_split, root=root))
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
    created_categories = []
    created_annotations = 0

    # Create any missing categories
    for category in coco_categories:

        category_name = category.get('name')
        category_id = category.get('id')
        # the same name can exist under several parents: the dataset's own
        # category first, then one under the file's parent, then any
        file_parents = CategoryModel.parse_parents(category.get('supercategories') or category.get('supercategory'))
        category_model = categories.filter(id__in=list(dataset.categories or []), name__iexact=category_name,
                                           deleted=False).first()
        if category_model is None and file_parents:
            category_model = categories.filter(name__iexact=category_name, supercategory=file_parents[0]).first()
        if category_model is None:
            category_model = categories.filter(name__iexact=category_name).first()

        if category_model is None:
            # expected when importing new classes, not a problem
            task.info(f"{category_name} category not found (creating a new one)")

            parents = CategoryModel.parse_parents(
                category.get('supercategories') or category.get('supercategory'))
            new_category = CategoryModel(
                name=category_name,
                keypoint_edges=category.get('skeleton', []),
                keypoint_labels=category.get('keypoints', []),
                supercategory=parents[0] if parents else '',
                supercategories=parents
            )
            new_category.save()
            created_categories.append(category_name)

            category_model = new_category
            dataset.categories.append(new_category.id)

        elif category_model.id not in dataset.categories:
            # the category exists (e.g. used by another dataset): add it here
            dataset.categories.append(category_model.id)

        if not category_model.parents() and (category.get('supercategories') or category.get('supercategory')):
            # an existing category without parents takes them from the file
            category_model.update(**category_model.set_parents(
                category.get('supercategories') or category.get('supercategory')))

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
            annotation_model.import_task = task_id  # lets the activity log take the import back
            annotation_model.source = 'import'      # statistics count these apart from people
            annotation_model.save()
            created_annotations += 1

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

    ActivityModel.objects(task_id=task_id, action='import').update(
        set__counts={'annotations': created_annotations, 'images': len(images_id),
                     'categories': len(created_categories)},
        set__detail__new_categories=created_categories[:50],
        set__updated_at=datetime.datetime.utcnow())

    task.set_progress(100, socket=socket)


__all__ = ["export_annotations", "import_annotations"]
