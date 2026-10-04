from flask_login import login_required, current_user
from flask_restx import Namespace, Resource, reqparse
from ..util.passwords import hash_password, check_password, check_and_upgrade

import re
import secrets

from database import UserModel, DatasetModel
from ..util.query_util import fix_ids

api = Namespace('admin', description='Admin related operations')

users = reqparse.RequestParser()
users.add_argument('limit', type=int, default=50)
users.add_argument('page', type=int, default=1)

create_user = reqparse.RequestParser()
create_user.add_argument('name', default="", location='json')
create_user.add_argument('password', default="", location='json')
create_user.add_argument('isAdmin', type=bool, default=None, location='json')

register = reqparse.RequestParser()
register.add_argument('username', required=True, location='json')
register.add_argument('password', required=True, location='json')
register.add_argument('email', location='json')
register.add_argument('name', location='json')
register.add_argument('isAdmin', type=bool, default=False, location='json')


bulk_users = reqparse.RequestParser()
bulk_users.add_argument('users', location='json', type=list, required=True,
                        help='[{"username": "B12345678", "name": "...", "password": "(optional)"}]')
bulk_users.add_argument('datasetId', location='json', type=int, default=None,
                        help='Optional dataset to share with the new (and existing) accounts')

STUDENT_ID = re.compile(r'^[A-Z][0-9]{8}$')
# no 0/O, 1/l/I: passwords are read from a printed list
PASSWORD_CHARS = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def _new_password(length=8):
    return ''.join(secrets.choice(PASSWORD_CHARS) for _ in range(length))


def _is_last_admin(user):
    return user.is_admin and UserModel.objects(is_admin=True).count() <= 1


@api.route('/users')
class Users(Resource):

    @api.expect(users)
    @login_required
    def get(self):
        """ Get list of all users """

        if not current_user.is_admin:
            return {"success": False, "message": "Access denied"}, 401

        args = users.parse_args()
        per_page = args['limit']
        page = args['page']-1

        user_model = UserModel.objects
        total = user_model.count()
        pages = int(total/per_page) + 1

        user_model = user_model.skip(page*per_page).limit(per_page).exclude("preferences", "password")

        return {
            "total": total,
            "pages": pages,
            "page": page,
            "per_page": per_page,
            "users": fix_ids(user_model.all())
        }


@api.route('/users/bulk')
class UsersBulk(Resource):

    @login_required
    @api.expect(bulk_users)
    def post(self):
        """ Create many accounts at once (student IDs like B12345678) """
        if not current_user.is_admin:
            return {"success": False, "message": "Access denied"}, 401

        args = bulk_users.parse_args()
        dataset = None
        if args.get('datasetId') is not None:
            dataset = DatasetModel.objects(id=args['datasetId'], deleted=False).first()
            if dataset is None:
                return {"success": False, "message": "Invalid dataset id"}, 400

        created, existing, invalid, seen = [], [], [], set()
        for row in args['users'] or []:
            row = row if isinstance(row, dict) else {}
            username = str(row.get('username') or '').strip().upper()
            name = str(row.get('name') or '').strip()
            password = str(row.get('password') or '').strip()

            if not STUDENT_ID.match(username):
                invalid.append({"username": username, "reason": "format"})
                continue
            if username in seen:
                invalid.append({"username": username, "reason": "duplicate"})
                continue
            seen.add(username)
            if UserModel.objects(username__iexact=username).first():
                existing.append(username)
                continue

            password = password or _new_password()
            user = UserModel(username=username, name=name or username,
                             password=hash_password(password), is_admin=False)
            user.save()
            created.append({"username": username, "name": user.name, "password": password})

        if dataset is not None:
            members = list(dataset.users or [])
            for username in [u["username"] for u in created] + existing:
                if username not in members:
                    members.append(username)
            dataset.update(users=members)

        return {"success": True, "created": created, "existing": existing, "invalid": invalid}


@api.route('/user/')
class User(Resource):

    @login_required
    @api.expect(register)
    def post(self):
        """ Create a new user """

        if not current_user.is_admin:
            return {"success": False, "message": "Access denied"}, 401

        args = register.parse_args()
        username = args.get('username')

        if UserModel.objects(username__iexact=username).first():
            return {'success': False, 'message': 'Username already exists.'}, 400

        user = UserModel()
        user.username = args.get('username')
        user.password = hash_password(args.get('password'))
        user.name = args.get('name', "")
        user.email = args.get('email', "")
        user.is_admin = args.get('isAdmin', False)
        user.save()

        user_json = fix_ids(current_user)
        del user_json['password']

        return {'success': True, 'user': user_json}


@api.route('/user/<string:username>')
class Username(Resource):

    @login_required
    def get(self, username):
        """ Get a users """

        if not current_user.is_admin:
            return {"success": False, "message": "Access denied"}, 401

        user = UserModel.objects(username__iexact=username).first()
        if user is None:
            return {"success": False, "message": "User not found"}, 400

        user_json = fix_ids(user)
        user_json.pop('password', None)
        return user_json

    @api.expect(create_user)
    @login_required
    def patch(self, username):
        """ Edit a user """

        if not current_user.is_admin:
            return {"success": False, "message": "Access denied"}, 401

        user = UserModel.objects(username__iexact=username).first()
        if user is None:
            return {"success": False, "message": "User not found"}, 400

        args = create_user.parse_args()
        name = args.get('name')
        if len(name) > 0:
            user.name = name

        password = args.get('password')
        if len(password) > 0:
            user.password = hash_password(password)

        is_admin = args.get('isAdmin')
        if is_admin is not None and bool(is_admin) != bool(user.is_admin):
            if not is_admin:
                if user.username.lower() == current_user.username.lower():
                    return {"success": False, "message": "You cannot remove your own admin rights."}, 400
                if _is_last_admin(user):
                    return {"success": False, "message": "At least one admin is required."}, 400
            user.is_admin = bool(is_admin)

        user.save()

        user_json = fix_ids(user)
        user_json.pop('password', None)
        return user_json

    @login_required
    def delete(self, username):
        """ Delete a user """

        if not current_user.is_admin:
            return {"success": False, "message": "Access denied"}, 401

        user = UserModel.objects(username__iexact=username).first()
        if user is None:
            return {"success": False, "message": "User not found"}, 400

        if user.username.lower() == current_user.username.lower():
            return {"success": False, "message": "You cannot delete your own account."}, 400
        if _is_last_admin(user):
            return {"success": False, "message": "At least one admin is required."}, 400

        user.delete()
        return {"success": True}

