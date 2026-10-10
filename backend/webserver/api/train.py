"""Training YOLO models on the server (the trainer service runs them, one
at a time). Needs the "train" permission."""
import datetime
import os
import shutil
import zipfile

from flask_login import login_required, current_user
from flask_restx import Namespace, Resource, reqparse
from mongoengine import Q

from database import DatasetModel, ExportModel, TrainRunModel, TrainerStatusModel
from trainer.runner import FAMILIES, SIZES, TASK_SUFFIX, base_weights, work_dir
from ..util import activity

api = Namespace('train', description='Train models on the server')

TRAINER_ALIVE_SECONDS = 30
TRAINABLE = tuple(TASK_SUFFIX)  # detect, segment, obb, pose, classify

create_args = reqparse.RequestParser()
create_args.add_argument('export_id', type=int, required=True, location='json')
create_args.add_argument('family', default='yolo26', location='json')
create_args.add_argument('size', default='n', location='json')
create_args.add_argument('base_model', default='', location='json',
                         help='Start from one of the models in the models folder instead')
create_args.add_argument('epochs', type=int, default=100, location='json')
create_args.add_argument('imgsz', type=int, default=640, location='json')
create_args.add_argument('batch', type=int, default=-1, location='json')
create_args.add_argument('patience', type=int, default=50, location='json')
create_args.add_argument('name', default='', location='json')


def _allowed():
    return current_user.has_perm('train')


def _export_ok(export):
    """The user may export every dataset of this export."""
    from .exports import export_dataset
    return export_dataset(export) is not None


def _task_of(export):
    tags = list(export.tags or [])
    return tags[1] if tags[:1] == ["YOLO"] and len(tags) > 1 else None


def _has_images(export):
    try:
        with zipfile.ZipFile(export.path) as zf:
            return any('/images/' in n or n.lower().endswith(('.jpg', '.jpeg', '.png')) for n in zf.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


@api.route('/status')
class TrainerStatus(Resource):

    @login_required
    def get(self):
        """ Is the trainer service running, on which device; queue length """
        if not _allowed():
            return {'message': 'No permission to train models'}, 403
        row = TrainerStatusModel.objects(key='trainer').first()
        alive = bool(row and row.seen_at and
                     (datetime.datetime.utcnow() - row.seen_at).total_seconds() < TRAINER_ALIVE_SECONDS)
        return {
            'alive': alive, 'device': row.device if row else '',
            'queued': TrainRunModel.objects(status='queued').count(),
            'running': TrainRunModel.objects(status='running').count(),
            'families': list(FAMILIES), 'sizes': list(SIZES), 'tasks': list(TRAINABLE),
        }


@api.route('/exports')
class TrainExports(Resource):

    @login_required
    def get(self):
        """ YOLO exports (with images) of the user's datasets that can be trained on """
        if not _allowed():
            return {'message': 'No permission to train models'}, 403
        out = []
        for dataset in current_user.datasets.filter(deleted=False).only('id', 'name', 'owner', 'users'):
            if not current_user.can_download(dataset):
                continue
            for export in ExportModel.objects(dataset_id=dataset.id).order_by('-id').limit(30):
                task = _task_of(export)
                if task not in TRAINABLE or not export.path or not os.path.isfile(export.path):
                    continue
                if not _has_images(export):
                    continue
                if getattr(export, 'dataset_ids', None) and not _export_ok(export):
                    continue
                out.append({
                    'id': export.id, 'task': task, 'dataset_id': dataset.id,
                    'datasets': list(getattr(export, 'dataset_names', None) or [dataset.name]),
                    'categories': list(export.tags or [])[2:],
                    'split': getattr(export, 'split', None),
                    'split_counts': getattr(export, 'split_counts', None),
                    'augment': getattr(export, 'augment', None),
                    'size': os.path.getsize(export.path),
                    'created_at': export.created_at.replace(microsecond=0).isoformat() + 'Z',
                })
        out.sort(key=lambda e: -e['id'])
        return {'exports': out}


@api.route('/')
class TrainRuns(Resource):

    @login_required
    def get(self):
        """ Training runs (everyone with the permission sees the shared queue) """
        if not _allowed():
            return {'message': 'No permission to train models'}, 403
        runs = TrainRunModel.objects.order_by('-id').limit(100)
        queued = [r.id for r in TrainRunModel.objects(status='queued').order_by('id').only('id')]
        out = []
        for r in runs:
            d = r.to_dict()
            d['queue_position'] = queued.index(r.id) + 1 if r.id in queued else None
            out.append(d)
        return {'runs': out}

    @api.expect(create_args)
    @login_required
    def post(self):
        """ Queue a training on a YOLO export """
        if not _allowed():
            return {'message': 'No permission to train models'}, 403
        args = create_args.parse_args()
        export = ExportModel.objects(id=args['export_id']).first()
        if export is None or not _export_ok(export):
            return {'message': 'Invalid export'}, 400
        task = _task_of(export)
        if task not in TRAINABLE:
            return {'message': 'Only YOLO exports (detect, segment, obb, pose, classify) can be trained on'}, 400
        if not export.path or not os.path.isfile(export.path) or not _has_images(export):
            return {'message': 'The export has no images: export again with "images in the zip"'}, 400

        if args.get('base_model'):
            from ..util.yolo import YoloService
            from config import Config
            try:
                YoloService(Config.MODELS_DIRECTORY).path_for(args['base_model'])
            except ValueError:
                return {'message': 'Unknown model'}, 400
            model = os.path.join(Config.MODELS_DIRECTORY, args['base_model'])
        else:
            if args['family'] not in FAMILIES or args['size'] not in SIZES:
                return {'message': 'Unknown model size'}, 400
            model = base_weights(args['family'], args['size'], task)
        epochs = max(1, min(int(args['epochs']), 1000))
        imgsz = max(32, min(int(args['imgsz']), 2048)) // 32 * 32
        batch = int(args['batch'])
        batch = -1 if batch < 1 else min(batch, 512)
        patience = max(0, min(int(args['patience']), 1000))

        dataset = DatasetModel.objects(id=export.dataset_id).first()
        names = list(getattr(export, 'dataset_names', None) or ([dataset.name] if dataset else []))
        run = TrainRunModel(
            name=(args.get('name') or '').strip()[:100] or " + ".join(names),
            creator=current_user.username, export_id=export.id, dataset_id=export.dataset_id,
            dataset_names=names, task=task, epochs=epochs,
            params={'model': model, 'base_model': args.get('base_model') or None,
                    'family': None if args.get('base_model') else args['family'],
                    'size': None if args.get('base_model') else args['size'],
                    'epochs': epochs, 'imgsz': imgsz, 'batch': batch, 'patience': patience})
        run.save()
        activity.record('train', current_user, dataset_id=export.dataset_id,
                        detail={'run': run.id, 'export_id': export.id, 'task': task, 'model': model,
                                'epochs': epochs}, text=f"{run.name} {task}")
        return run.to_dict()


@api.route('/<int:run_id>')
class TrainRun(Resource):

    @login_required
    def get(self, run_id):
        if not _allowed():
            return {'message': 'No permission to train models'}, 403
        run = TrainRunModel.objects(id=run_id).first()
        if run is None:
            return {'message': 'Invalid run'}, 400
        return run.to_dict(full=True)

    @login_required
    def delete(self, run_id):
        """ Remove a finished run (its working files; a trained model stays) """
        if not _allowed():
            return {'message': 'No permission to train models'}, 403
        run = TrainRunModel.objects(id=run_id).first()
        if run is None:
            return {'message': 'Invalid run'}, 400
        if run.status in ('queued', 'running'):
            return {'message': 'Stop it first'}, 400
        if run.creator != current_user.username and not current_user.is_admin:
            return {'message': 'Only its creator or an admin can remove it'}, 403
        shutil.rmtree(work_dir(run.id), ignore_errors=True)
        run.delete()
        return {'success': True}


@api.route('/<int:run_id>/stop')
class TrainRunStop(Resource):

    @login_required
    def post(self, run_id):
        """ Stop a running training (the weights so far are kept) or cancel a queued one """
        if not _allowed():
            return {'message': 'No permission to train models'}, 403
        run = TrainRunModel.objects(id=run_id).first()
        if run is None:
            return {'message': 'Invalid run'}, 400
        if run.creator != current_user.username and not current_user.is_admin:
            return {'message': 'Only its creator or an admin can stop it'}, 403
        if run.status == 'queued':
            TrainRunModel.objects(id=run.id, status='queued').update_one(
                set__status='stopped', set__ended_at=datetime.datetime.utcnow())
        elif run.status == 'running':
            run.update(set__stop_requested=True)
        return TrainRunModel.objects(id=run.id).first().to_dict()
