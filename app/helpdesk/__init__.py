from flask import Blueprint

helpdesk_bp = Blueprint('helpdesk', __name__)

from .helpdesk import *
