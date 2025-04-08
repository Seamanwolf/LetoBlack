from flask import Blueprint
callcenter_bp = Blueprint('callcenter', __name__)
from . import callcenter
from .callcenter import partial_sync_data
