from flask import Blueprint

leader_bp = Blueprint('leader', __name__, template_folder='templates')

from .leader import *
