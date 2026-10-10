"""Chat: one room per dataset. Members (anyone who can open the dataset)
read and write; a message can point at one of the dataset's images."""
from flask_login import login_required, current_user
from flask_restx import Namespace, Resource, reqparse

from database import ChatMessageModel, ChatReadModel, ImageModel, UserModel

api = Namespace('chat', description='Chat per dataset')

MAX_TEXT = 1000
PAGE = 50

list_args = reqparse.RequestParser()
list_args.add_argument('before', type=int, default=None, location='args')
list_args.add_argument('limit', type=int, default=PAGE, location='args')

post_args = reqparse.RequestParser()
post_args.add_argument('text', default='', location='json')
post_args.add_argument('image_id', type=int, default=None, location='json')

read_args = reqparse.RequestParser()
read_args.add_argument('last_id', type=int, required=True, location='json')


def _dataset(dataset_id):
    return current_user.datasets.filter(id=dataset_id, deleted=False).first()


def _names(usernames):
    return {u.username: u.name or u.username
            for u in UserModel.objects(username__in=list(set(usernames))).only('username', 'name')}


def _last_read(dataset_id):
    row = ChatReadModel.objects(user=current_user.username, dataset_id=dataset_id).first()
    return row.last_id if row else 0


def _unread(dataset_id):
    return ChatMessageModel.objects(dataset_id=dataset_id, id__gt=_last_read(dataset_id),
                                    user__ne=current_user.username).count()


@api.route('/dataset/<int:dataset_id>')
class DatasetChat(Resource):

    @login_required
    def get(self, dataset_id):
        """Messages, oldest first (``before`` pages back)"""
        if _dataset(dataset_id) is None:
            return {'message': 'Invalid dataset id'}, 400
        args = list_args.parse_args()
        limit = max(1, min(args['limit'] or PAGE, 200))
        query = ChatMessageModel.objects(dataset_id=dataset_id)
        if args['before']:
            query = query.filter(id__lt=args['before'])
        rows = list(query.order_by('-id').limit(limit + 1))
        more = len(rows) > limit
        rows = list(reversed(rows[:limit]))
        names = _names([m.user for m in rows])
        return {
            'messages': [m.to_dict(names) for m in rows],
            'more': more,
            'last_read': _last_read(dataset_id),
            'unread': _unread(dataset_id),
            'me': current_user.username,
        }

    @login_required
    def post(self, dataset_id):
        """Send a message to the dataset's room"""
        if _dataset(dataset_id) is None:
            return {'message': 'Invalid dataset id'}, 400
        args = post_args.parse_args()
        text = (args.get('text') or '').strip()
        image = None
        if args.get('image_id') is not None:
            image = ImageModel.objects(id=args['image_id'], dataset_id=dataset_id, deleted=False) \
                .only('id', 'file_name').first()
            if image is None:
                return {'message': 'Image not in this dataset'}, 400
        if not text and image is None:
            return {'message': 'Empty message'}, 400
        if len(text) > MAX_TEXT:
            return {'message': f'At most {MAX_TEXT} characters'}, 400

        message = ChatMessageModel(dataset_id=dataset_id, user=current_user.username, text=text,
                                   image_id=image.id if image else None,
                                   file_name=image.file_name if image else '')
        message.save()
        data = message.to_dict({current_user.username: current_user.name})
        # it counts as read for the sender
        ChatReadModel.objects(user=current_user.username, dataset_id=dataset_id) \
            .update_one(set__last_id=message.id, upsert=True)

        from ..sockets import socketio, chat_room
        socketio.emit('chat', data, room=chat_room(dataset_id))
        return data


@api.route('/dataset/<int:dataset_id>/read')
class DatasetChatRead(Resource):

    @login_required
    def post(self, dataset_id):
        """Everything up to ``last_id`` has been seen"""
        if _dataset(dataset_id) is None:
            return {'message': 'Invalid dataset id'}, 400
        last_id = read_args.parse_args()['last_id']
        if last_id > _last_read(dataset_id):
            ChatReadModel.objects(user=current_user.username, dataset_id=dataset_id) \
                .update_one(set__last_id=last_id, upsert=True)
        return {'unread': _unread(dataset_id)}
