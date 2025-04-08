# app/avito/__init__.py
from flask import Blueprint

# Создаем Blueprint для "Авито Про"
avito_bp = Blueprint('avito', __name__)

# Импортируем маршруты из avito.py
from . import avito
