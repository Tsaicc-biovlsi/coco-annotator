
from config import Config


bind = '0.0.0.0:5000'
backlog = 2048

workers = 1
# Flask-SocketIO runs in threading mode (simple-websocket), so a single
# gthread worker with many threads handles both HTTP and websockets.
# Every open page keeps a websocket, which holds one thread while it is
# open: allow for ~3 pages per user (WEB_THREADS, default 300 = ~100 users).
worker_class = 'gthread'
threads = Config.WEB_THREADS
timeout = 180
keepalive = 2

reload = Config.DEBUG
preload = Config.PRELOAD

errorlog = '-'
loglevel = Config.LOG_LEVEL
accesslog = None