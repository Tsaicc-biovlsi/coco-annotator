
from flask_login import current_user
from mongoengine import *

from .colors import random_color


class CategoryModel(DynamicDocument):

    COCO_PROPERTIES = ["id", "name", "supercategory", "supercategories", "color", "metadata",\
                       "keypoint_edges", "keypoint_labels", "keypoint_colors"]

    id = SequenceField(primary_key=True)
    name = StringField(required=True, unique_with=['creator'])
    #: COCO's single parent: the first of ``supercategories``
    supercategory = StringField(default='')
    #: all parent categories (a category can be in several groups)
    supercategories = ListField(StringField(), default=[])
    color = StringField(default=None)
    metadata = DictField(default={})

    creator = StringField(default='unknown')
    deleted = BooleanField(default=False)
    deleted_date = DateTimeField()

    keypoint_edges = ListField(default=[])
    keypoint_labels = ListField(default=[])
    keypoint_colors = ListField(default=[])

    @staticmethod
    def parse_parents(value):
        """A list or "a, b、c" -> unique, trimmed parent names (in order)."""
        import re
        if value is None:
            return []
        items = value if isinstance(value, (list, tuple)) else re.split(r"[,，、;；\n]+", str(value))
        out = []
        for item in items:
            name = str(item or '').strip()
            if name and name not in out:
                out.append(name)
        return out[:20]

    def parents(self):
        return list(self.supercategories or []) or self.parse_parents(self.supercategory)

    def set_parents(self, parents):
        """Fields to update for these parents (supercategory = the first one)."""
        parents = self.parse_parents(parents)
        return {'supercategories': parents, 'supercategory': parents[0] if parents else ''}

    @classmethod
    def bulk_create(cls, categories):

        if not categories:
            return []

        category_ids = []
        for category in categories:
            category_model = CategoryModel.objects(name=category).first()

            if category_model is None:
                new_category = CategoryModel(name=category)
                new_category.save()
                category_ids.append(new_category.id)
            else:
                category_ids.append(category_model.id)

        return category_ids

    def save(self, *args, **kwargs):

        if not self.color:
            self.color = random_color()

        if current_user:
            self.creator = current_user.username
        else:
            self.creator = 'system'
      
        return super(CategoryModel, self).save(*args, **kwargs)

    
    def is_owner(self, user):

        if user.is_admin:
            return True
        
        return user.username.lower() == self.creator.lower()
    
    def can_edit(self, user):
        return self.is_owner(user)
    
    def can_delete(self, user):
        return self.is_owner(user)


__all__ = ["CategoryModel"]