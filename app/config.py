SECRET_KEY = 'Gfzkmybr72'

import os

class Config:
    SECRET_KEY = 'Gfzkmybr72'
    STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    STATIC_URL_PATH = '/static'

