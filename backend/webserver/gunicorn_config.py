
from config import Config


bind = '0.0.0.0:5000'
backlog = 2048

workers = 1
# Flask-SocketIO runs in threading mode (simple-websocket), so a single
# gthread worker with many threads handles both HTTP and websockets.
worker_class = 'gthread'
threads = 100
timeout = 180
keepalive = 2

reload = Config.DEBUG
preload = Config.PRELOAD

errorlog = '-'
loglevel = Config.LOG_LEVEL
accesslog = None