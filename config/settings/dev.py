from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']
CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5177",
    "http://127.0.0.1:5177",
]
CORS_ALLOW_CREDENTIALS = True

# Debug-specific tools can be added here
