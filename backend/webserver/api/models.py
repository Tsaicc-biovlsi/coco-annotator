from flask_restx import Namespace, Resource, reqparse
from flask_login import login_required, current_user

from database import ImageModel
from ..util.sam import sam
from ..util.yolo import yolo
from ..util import preannotate
from ..sockets import socketio

import logging

logger = logging.getLogger('gunicorn.error')

api = Namespace('model', description='AI-assisted annotation (Segment Anything, your YOLO models)')


sam_args = reqparse.RequestParser()
sam_args.add_argument('points', location='json', type=list, default=[],
                      help='[[x, y], ...] prompt points in image pixels')
sam_args.add_argument('labels', location='json', type=list, default=[],
                      help='1 = foreground, 0 = background, one per point')
sam_args.add_argument('box', location='json', type=list, default=None,
                      help='[x1, y1, x2, y2] prompt box in image pixels')


@api.route('/')
class ModelStatus(Resource):

    @login_required
    def get(self):
        """ Which AI-assist models are available """
        return {"sam": sam.status(), "yolo": yolo.status()}


@api.route('/sam/<int:image_id>')
class SegmentAnything(Resource):

    @login_required
    @api.expect(sam_args)
    def post(self, image_id):
        """ Segment an object from point and/or box prompts """
        if not sam.available:
            return {"disabled": True, "message": "SAM is not available on this server"}, 400

        args = sam_args.parse_args()
        points = args.get('points') or []
        labels = args.get('labels') or []
        box = args.get('box')

        if not points and not box:
            return {"message": "Provide at least one point or a box"}, 400
        if labels and len(labels) != len(points):
            return {"message": "labels must match points"}, 400
        if box is not None and len(box) != 4:
            return {"message": "box must be [x1, y1, x2, y2]"}, 400

        image_model = ImageModel.objects(id=image_id).first()
        if not image_model:
            return {"message": "Invalid image ID"}, 400

        try:
            polygons, score, area = sam.predict(
                image_id, image_model.path, points=points, labels=labels, box=box
            )
        except Exception as e:
            logger.exception("SAM prediction failed")
            return {"message": f"SAM prediction failed: {e}"}, 500

        return {"segmentation": polygons, "score": score, "area": area}


@api.route('/sam/<int:image_id>/prepare')
class SegmentAnythingPrepare(Resource):

    @login_required
    def post(self, image_id):
        """ Start computing the SAM image embedding in the background """
        if not sam.available:
            return {"disabled": True, "message": "SAM is not available on this server"}, 400

        image_model = ImageModel.objects(id=image_id).first()
        if not image_model:
            return {"message": "Invalid image ID"}, 400

        sam.prepare_async(image_id, image_model.path)
        return {"success": True}


yolo_args = reqparse.RequestParser()
yolo_args.add_argument('model', location='json', required=True, help='Model file (.pt) name')
yolo_args.add_argument('conf', location='json', type=float, default=0.25,
                       help='Minimum confidence (0-1)')
yolo_args.add_argument('create_categories', location='json', type=bool, default=True,
                       help='Create categories for classes the dataset does not have')
yolo_args.add_argument('skip_annotated', location='json', type=bool, default=True,
                       help='Dataset only: skip images that already have annotations')


def _check_model(name):
    if not yolo.installed:
        return {"disabled": True, "message": "Model support is not installed on this server"}, 400
    try:
        yolo.path_for(name)
    except ValueError:
        return {"message": "Unknown model"}, 400
    return None


def _conf(value):
    return min(max(float(value), 0.01), 1.0)


@api.route('/yolo')
class YoloModels(Resource):

    @login_required
    def get(self):
        """ Your models (.pt files in the models folder) with task and classes """
        if not yolo.installed:
            return {"installed": False, "models": []}
        return {"installed": True, "models": yolo.list()}


@api.route('/yolo/image/<int:image_id>')
class YoloImage(Resource):

    @login_required
    @api.expect(yolo_args)
    def post(self, image_id):
        """ Run a model on one image and save the predictions as annotations """
        args = yolo_args.parse_args()
        error = _check_model(args['model'])
        if error:
            return error

        image = current_user.images.filter(id=image_id, deleted=False).first()
        if image is None:
            return {"message": "Invalid image ID"}, 400
        if not current_user.can_edit(image.dataset):
            return {"message": "You do not have permission to edit this dataset"}, 403

        try:
            result = preannotate.annotate_image(
                image, args['model'], conf=_conf(args['conf']),
                create_missing=args['create_categories'],
                user=current_user._get_current_object())
        except Exception as e:
            logger.exception("Model prediction failed")
            return {"message": f"Model prediction failed: {e}"}, 500
        return result


@api.route('/yolo/dataset/<int:dataset_id>')
class YoloDataset(Resource):

    @login_required
    @api.expect(yolo_args)
    def post(self, dataset_id):
        """ Run a model over a whole dataset in the background (a task) """
        args = yolo_args.parse_args()
        error = _check_model(args['model'])
        if error:
            return error

        dataset = current_user.datasets.filter(id=dataset_id, deleted=False).first()
        if dataset is None:
            return {"message": "Invalid dataset ID"}, 400
        if not current_user.can_edit(dataset):
            return {"message": "You do not have permission to edit this dataset"}, 403

        return preannotate.annotate_dataset(
            dataset, args['model'], conf=_conf(args['conf']),
            skip_annotated=args['skip_annotated'],
            create_missing=args['create_categories'],
            user=current_user._get_current_object(),
            socket=socketio)
