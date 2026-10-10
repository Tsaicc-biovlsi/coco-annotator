"""Chat: one room per dataset, for its members."""
import datetime

from mongoengine import DynamicDocument, SequenceField, IntField, StringField, DateTimeField


class ChatMessageModel(DynamicDocument):
    id = SequenceField(primary_key=True)
    dataset_id = IntField(required=True)
    user = StringField(required=True)
    text = StringField(default='')
    #: the image the message is about (optional, from the annotator)
    image_id = IntField()
    file_name = StringField(default='')
    created_at = DateTimeField(default=datetime.datetime.utcnow)

    meta = {'collection': 'chat_message', 'indexes': [('dataset_id', '-id')]}

    def to_dict(self, names=None):
        return {
            'id': self.id, 'dataset_id': self.dataset_id, 'user': self.user,
            'name': (names or {}).get(self.user) or self.user,
            'text': self.text, 'image_id': self.image_id, 'file_name': self.file_name or '',
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }


class ChatReadModel(DynamicDocument):
    """The last message a user has seen in a dataset's room."""
    user = StringField(required=True)
    dataset_id = IntField(required=True)
    last_id = IntField(default=0)

    meta = {'collection': 'chat_read', 'indexes': [{'fields': ['user', 'dataset_id'], 'unique': True}]}
