from flask import Blueprint

# Blueprint для брокерского интерфейса
broker_bp = Blueprint('broker', __name__, url_prefix='/broker')

# Импорт маршрутов (важно для регистрации)
from . import broker  # noqa: E402 