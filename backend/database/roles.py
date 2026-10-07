"""Roles (身分): what a user may see and manage beyond their own datasets.

Two are built in and cannot be deleted: ``admin`` (everything, always) and
``user`` (the default for new accounts; its permissions can be changed).
Admins add their own (e.g. 助教) with any mix of PERMISSIONS."""
from mongoengine import DynamicDocument, StringField, ListField, BooleanField, IntField

# pages first, then management rights
PAGES = ('activity', 'models', 'tasks')
MANAGE = ('manage_models', 'manage_users', 'all_datasets')
PERMISSIONS = PAGES + MANAGE

ADMIN = 'admin'
DEFAULT = 'user'


class RoleModel(DynamicDocument):
    key = StringField(primary_key=True)
    name = StringField(default='')
    permissions = ListField(StringField(), default=list)
    builtin = BooleanField(default=False)
    order = IntField(default=100)

    meta = {'collection': 'role_model'}

    @staticmethod
    def clean_permissions(perms):
        return [p for p in PERMISSIONS if p in (perms or [])]

    @classmethod
    def ensure_builtin(cls):
        if cls.objects(key=ADMIN).first() is None:
            cls(key=ADMIN, name='', permissions=list(PERMISSIONS), builtin=True, order=0).save()
        if cls.objects(key=DEFAULT).first() is None:
            cls(key=DEFAULT, name='', permissions=[], builtin=True, order=1).save()

    @classmethod
    def all_ordered(cls):
        cls.ensure_builtin()
        return list(cls.objects.order_by('order', 'name'))

    @classmethod
    def permissions_of(cls, key):
        if key == ADMIN:
            return set(PERMISSIONS)
        role = cls.objects(key=key or DEFAULT).first() or cls.objects(key=DEFAULT).first()
        return set(role.permissions or []) if role else set()

    def to_dict(self, users=None):
        out = {'key': self.key, 'name': self.name or '', 'builtin': bool(self.builtin),
               'permissions': self.clean_permissions(self.permissions) if self.key != ADMIN else list(PERMISSIONS)}
        if users is not None:
            out['users'] = users
        return out
