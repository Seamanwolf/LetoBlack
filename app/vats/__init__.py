from flask import Blueprint

vats_bp = Blueprint('vats', __name__)

from .vats import *
