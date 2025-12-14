from app import app

# Expose a WSGI-compatible application object for gunicorn/uwsgi.
application = app
