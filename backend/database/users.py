import datetime

from mongoengine import *
from flask_login import UserMixin

from .annotations import AnnotationModel
from .categories import CategoryModel
from .datasets import DatasetModel
from .images import ImageModel


class UserModel(DynamicDocument, UserMixin):

    password = StringField(required=True)
    username = StringField(max_length=25, required=True, unique=True)
    email = StringField(max_length=30)

    name = StringField()
    online = BooleanField(default=False)
    last_seen = DateTimeField()

    is_admin = BooleanField(default=False)

    preferences = DictField(default={})
    permissions = ListField(defualt=[])

    # meta = {'allow_inheritance': True}

    @classmethod
    def total(cls):
        """Exact number of users.

        ``objects.count()`` without a filter uses MongoDB's collection
        metadata, which can be stale (e.g. 0 after an unclean shutdown). This
        decides whether registration is open and who becomes admin, so count
        the documents.
        """
        return cls._get_collection().count_documents({})

    @property
    def datasets(self):
        self._update_last_seen()

        if self.is_admin:
            return DatasetModel.objects

        return DatasetModel.objects(Q(owner=self.username) | Q(users__contains=self.username))

    @property
    def categories(self):
        self._update_last_seen()

        if self.is_admin:
            return CategoryModel.objects

        dataset_ids = self.datasets.distinct('categories')
        return CategoryModel.objects(Q(id__in=dataset_ids) | Q(creator=self.username))

    @property
    def images(self):
        self._update_last_seen()

        if self.is_admin:
            return ImageModel.objects

        dataset_ids = self.datasets.distinct('id')
        return ImageModel.objects(dataset_id__in=dataset_ids)

    @property
    def annotations(self):
        self._update_last_seen()

        if self.is_admin:
            return AnnotationModel.objects

        image_ids = self.images.distinct('id')
        return AnnotationModel.objects(image_id__in=image_ids)

    def can_view(self, model):
        if model is None:
            return False

        return model.can_view(self)
    
    def can_download(self, model):
        if model is None:
            return False

        return model.can_download(self)
        
    def can_delete(self, model):
        if model is None:
            return False
        return model.can_delete(self)

    def can_edit(self, model):
        if model is None:
            return False

        return model.can_edit(self)

    def _update_last_seen(self):
        # called on most requests (several times each): write at most once a
        # minute instead of on every image / thumbnail request
        now = datetime.datetime.utcnow()
        last = getattr(self, 'last_seen', None)
        if isinstance(last, datetime.datetime) and (now - last).total_seconds() < 60:
            return
        self.last_seen = now
        self.update(last_seen=now)
    


__all__ = ["UserModel"]