from flask import Blueprint
userlist_bp = Blueprint('userlist', __name__)
from . import userlist
