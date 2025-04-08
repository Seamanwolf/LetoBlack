from flask import Blueprint

itinvent_bp = Blueprint('itinvent', __name__)

from . import itinvent
