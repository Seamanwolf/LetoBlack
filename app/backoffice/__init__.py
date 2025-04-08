from flask import Blueprint
backoffice_bp = Blueprint('backoffice', __name__)
from .backoffice import *
