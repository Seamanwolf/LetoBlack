from flask import Blueprint

rating_bp = Blueprint('rating', __name__)

from .rating import *
