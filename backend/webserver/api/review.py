"""Review workflow: image status, assignment of images to members, progress.

Status of an image:

* ``unlabeled`` - nobody has submitted it yet (default)
* ``labeled``   - an annotator pressed "done" (waiting for review)
* ``approved``  - a reviewer accepted it
* ``rejected``  - a reviewer sent it back, with a note

Reviewers are the dataset owner, admins and the members listed in
``dataset.reviewers``. Anyone who can edit the dataset can submit.
"""
import datetime

from flask_login import login_required, current_user
from flask_restx import Namespace, Resource, reqparse
from mongoengine.queryset.visitor import Q

from database import DatasetModel, ImageModel

api = Namespace('review', description='Image status, assignment and review')

status_args = reqparse.RequestParser()
status_args.add_argument('action', location='json', required=True,
                         choices=('submit', 'approve', 'reject', 'reopen'))
status_args.add_argument('note', location='json', default='')
status_args.add_argument('image_ids', location='json', type=list, default=None,
                         help='Apply to several images of the same dataset')

assign_args = reqparse.RequestParser()
assign_args.add_argument('usernames', location='json', type=list, default=[],
                         help='Members to assign to (empty: unassign)')
assign_args.add_argument('image_ids', location='json', type=list, default=None,
                         help='Images to assign (default: every image that matches "scope")')
assign_args.add_argument('scope', location='json', default='unassigned',
                         choices=('unassigned', 'all', 'unlabeled'),
                         help='Which images when image_ids is not given')

reviewers_args = reqparse.RequestParser()
reviewers_args.add_argument('reviewers', location='json', type=list, default=[])


def _dataset(dataset_id):
    return current_user.datasets.filter(id=dataset_id, deleted=False).first()


def image_review_info(image):
    def iso(value):
        return value.isoformat() + 'Z' if value else None
    return {
        'status': image.status or 'unlabeled',
        'assignee': image.assignee,
        'labeled_by': image.labeled_by,
        'labeled_at': iso(image.labeled_at),
        'reviewed_by': image.reviewed_by,
        'reviewed_at': iso(image.reviewed_at),
        'review_note': image.review_note,
    }


def change_status(images, dataset, action, note=''):
    """Apply ``action`` to the images. Returns (count, error message or None)."""
    now = datetime.datetime.utcnow()
    me = current_user.username
    if action in ('approve', 'reject'):
        if not dataset.can_review(current_user):
            return 0, 'Only reviewers can approve or reject images'
    elif not current_user.can_edit(dataset):
        return 0, 'You do not have permission to edit this dataset'

    count = 0
    for image in images:
        if action == 'submit':
            image.update(set__status='labeled', set__labeled_by=me, set__labeled_at=now)
        elif action == 'approve':
            image.update(set__status='approved', set__reviewed_by=me, set__reviewed_at=now,
                         set__review_note='')
        elif action == 'reject':
            image.update(set__status='rejected', set__reviewed_by=me, set__reviewed_at=now,
                         set__review_note=(note or '').strip()[:2000])
        elif action == 'reopen':
            # back to work; an approved image can only be reopened by a reviewer
            if image.status == 'approved' and not dataset.can_review(current_user):
                continue
            image.update(set__status='unlabeled')
        count += 1
    return count, None


@api.route('/image/<int:image_id>')
class ImageStatus(Resource):

    @login_required
    def get(self, image_id):
        image = current_user.images.filter(id=image_id, deleted=False).first()
        if image is None:
            return {'message': 'Invalid image id'}, 400
        return image_review_info(image)

    @api.expect(status_args)
    @login_required
    def post(self, image_id):
        """ submit / approve / reject / reopen one image (or several with image_ids) """
        args = status_args.parse_args()
        image = current_user.images.filter(id=image_id, deleted=False).first()
        if image is None:
            return {'message': 'Invalid image id'}, 400
        dataset = _dataset(image.dataset_id)
        if dataset is None:
            return {'message': 'Invalid dataset'}, 400

        images = [image]
        if args.get('image_ids'):
            ids = [int(i) for i in args['image_ids']]
            images = list(ImageModel.objects(id__in=ids, dataset_id=dataset.id, deleted=False))

        count, error = change_status(images, dataset, args['action'], args.get('note'))
        if error:
            return {'message': error}, 403
        image.reload()
        return {'success': True, 'count': count, **image_review_info(image)}


@api.route('/dataset/<int:dataset_id>/assign')
class DatasetAssign(Resource):

    @api.expect(assign_args)
    @login_required
    def post(self, dataset_id):
        """ Split images evenly between members (or unassign with no usernames) """
        args = assign_args.parse_args()
        dataset = _dataset(dataset_id)
        if dataset is None:
            return {'message': 'Invalid dataset id'}, 400
        if not dataset.can_review(current_user):
            return {'message': 'Only the owner or reviewers can assign images'}, 403

        members = {u.username for u in dataset.get_users()}
        usernames = [u for u in (args.get('usernames') or []) if u]
        unknown = [u for u in usernames if u not in members]
        if unknown:
            return {'message': 'Not members of this dataset: ' + ', '.join(unknown)}, 400

        query = ImageModel.objects(dataset_id=dataset.id, deleted=False)
        if args.get('image_ids') is not None:
            query = query.filter(id__in=[int(i) for i in args['image_ids']])
        elif args['scope'] == 'unassigned':
            query = query.filter(Q(assignee=None) | Q(assignee=''))
        elif args['scope'] == 'unlabeled':
            query = query.filter(Q(status=None) | Q(status__in=['unlabeled', 'rejected']))
        images = list(query.order_by('file_name').only('id'))

        if not usernames:
            ImageModel.objects(id__in=[i.id for i in images]).update(unset__assignee=True)
            return {'success': True, 'assigned': {}, 'unassigned': len(images)}

        # contiguous blocks in file name order: each person gets a range
        counts = {}
        per_person = -(-len(images) // len(usernames)) if images else 0
        for n, username in enumerate(usernames):
            block = images[n * per_person:(n + 1) * per_person]
            if block:
                ImageModel.objects(id__in=[i.id for i in block]).update(set__assignee=username)
            counts[username] = len(block)
        return {'success': True, 'assigned': counts, 'unassigned': 0}


@api.route('/dataset/<int:dataset_id>/progress')
class DatasetProgress(Resource):

    @login_required
    def get(self, dataset_id):
        """ Images per status, overall and per assignee """
        dataset = _dataset(dataset_id)
        if dataset is None:
            return {'message': 'Invalid dataset id'}, 400

        statuses = ImageModel.STATUSES
        total = {s: 0 for s in statuses}
        people = {}
        for row in ImageModel.objects(dataset_id=dataset.id, deleted=False) \
                .only('status', 'assignee', 'labeled_by', 'num_annotations').as_pymongo():
            status = row.get('status') or 'unlabeled'
            total[status] = total.get(status, 0) + 1
            who = row.get('assignee') or ''
            person = people.setdefault(who, {s: 0 for s in statuses})
            person[status] += 1

        members = [u.username for u in dataset.get_users()]
        return {
            'total': total,
            'images': sum(total.values()),
            'people': [{'username': name, **counts} for name, counts in sorted(people.items()) if name],
            'unassigned': people.get('', {s: 0 for s in statuses}),
            'members': members,
            'reviewers': list(dataset.reviewers or []),
            'can_review': dataset.can_review(current_user),
            'is_owner': dataset.is_owner(current_user),
            'me': current_user.username,
            'owner': dataset.owner,
        }


@api.route('/dataset/<int:dataset_id>/reviewers')
class DatasetReviewers(Resource):

    @api.expect(reviewers_args)
    @login_required
    def post(self, dataset_id):
        """ Set which members may approve / reject (owner only) """
        args = reviewers_args.parse_args()
        dataset = _dataset(dataset_id)
        if dataset is None:
            return {'message': 'Invalid dataset id'}, 400
        if not dataset.is_owner(current_user):
            return {'message': 'Only the owner can choose reviewers'}, 403
        members = {u.username for u in dataset.get_users()}
        reviewers = sorted({u for u in args.get('reviewers') or [] if u in members})
        dataset.update(set__reviewers=reviewers)
        return {'success': True, 'reviewers': reviewers}


@api.route('/dataset/<int:dataset_id>/next')
class DatasetNextImage(Resource):

    @login_required
    def get(self, dataset_id):
        """ Next image to work on: for reviewers the next "labeled" one, for
        others the next of their own unlabeled / rejected images """
        from flask import request
        dataset = _dataset(dataset_id)
        if dataset is None:
            return {'message': 'Invalid dataset id'}, 400
        mode = request.args.get('mode', 'review')
        after = request.args.get('after', '')
        query = ImageModel.objects(dataset_id=dataset.id, deleted=False)
        if mode == 'review':
            query = query.filter(status='labeled')
        else:
            query = query.filter(assignee=current_user.username) \
                .filter(Q(status=None) | Q(status__in=['unlabeled', 'rejected']))
        image = query.filter(file_name__gt=after).order_by('file_name').only('id').first() \
            or query.order_by('file_name').only('id').first()
        return {'id': image.id if image else None}


__all__ = ['api', 'image_review_info', 'change_status']
