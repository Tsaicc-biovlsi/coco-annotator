import functools
import time

from flask import session, request
from flask_socketio import (
    SocketIO,
    disconnect,
    join_room,
    leave_room,
    emit
)
from flask_login import current_user

from database import ImageModel, SessionEvent
from config import Config

import logging
logger = logging.getLogger('gunicorn.error')


# Before the connection is upgraded to a websocket (and when a proxy keeps it
# on long-polling), the browser sends its queued messages in one request. The
# annotator emits an event per edit, so 16 (Engine.IO's default limit) is
# easily passed: "Too many packets in payload" and the socket is dropped.
from engineio.payload import Payload
Payload.max_decode_packets = 1000

socketio = SocketIO(async_mode='threading')

# who has the app open right now: username -> socket ids (one web worker)
ONLINE = {}


def is_online(username):
    return bool(ONLINE.get(username))


def _join_user():
    if not current_user.is_authenticated:
        return
    join_room(user_room(current_user.username))
    ONLINE.setdefault(current_user.username, set()).add(request.sid)


def user_room(username):
    return f"user:{username}"


def notify_user(username, event, data):
    """Push to every page that user has open"""
    socketio.emit(event, data, room=user_room(username))


def authenticated_only(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if current_user.is_authenticated or Config.LOGIN_DISABLED:
            return f(*args, **kwargs)
        else:
            disconnect()
    return wrapped


@socketio.on('annotation')
@authenticated_only
def annotation(data):
    emit('annotation', data, broadcast=True)


@socketio.on('annotating')
@authenticated_only
def annotating(data):
    """
    Socket for handling image locking and time logging
    """

    image_id = data.get('image_id')
    active = data.get('active')
    
    image = ImageModel.objects(id=image_id).first()
    if image is None:
        # invalid image ID
        return
    
    emit('annotating', {
        'image_id': image_id,
        'active': active,
        'username': current_user.username
    }, broadcast=True, include_self=False)

    if active:
        logger.info(f'{current_user.username} has started annotating image {image_id}')
        # Remove user from pervious room
        previous = session.get('annotating')
        if previous is not None:
            leave_room(previous)
            previous_image = ImageModel.objects(id=previous).first()

            if previous_image is not None:

                start = session.get('annotating_time', time.time())
                event = SessionEvent.create(start, current_user)

                previous_image.add_event(event)
                previous_image.update(
                    pull__annotating=current_user.username
                )

                emit('annotating', {
                    'image_id': previous,
                    'active': False,
                    'username': current_user.username
                }, broadcast=True, include_self=False)

        join_room(image_id)
        session['annotating'] = image_id
        session['annotating_time'] = time.time()
        image.update(add_to_set__annotating=current_user.username)
    else:
        leave_room(image_id)

        start = session.get('annotating_time', time.time())
        event = SessionEvent.create(start, current_user)

        image.add_event(event)
        image.update(
            pull__annotating=current_user.username
        )

        session['annotating'] = None
        session['time'] = None


@socketio.on('connect')
def connect():
    logger.info(f'Socket connection created with {current_user.username}')
    _join_user()


@socketio.on('join_user')
def join_user(data=None):
    """Sent by the page once it knows who is logged in. The socket keeps the
    session it connected with: False tells a page that logged in after
    connecting to reconnect."""
    _join_user()
    return bool(current_user.is_authenticated)


@socketio.on('disconnect')
def disconnect():
    if current_user.is_authenticated:
        logger.info(f'Socket connection has been disconnected with {current_user.username}')
        sids = ONLINE.get(current_user.username)
        if sids is not None:
            sids.discard(request.sid)
            if not sids:
                ONLINE.pop(current_user.username, None)
        image_id = session.get('annotating')

        # Remove user from room
        if image_id is not None:
            image = ImageModel.objects(id=image_id).first()
            if image is not None:
                start = session.get('annotating_time', time.time())
                event = SessionEvent.create(start, current_user)
        
                image.add_event(event)
                image.update(
                    pull__annotating=current_user.username
                )
                emit('annotating', {
                    'image_id': image_id,
                    'active': False,
                    'username': current_user.username
                }, broadcast=True, include_self=False)
               
