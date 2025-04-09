from flask import jsonify
from app.routes.api import api_bp

@api_bp.route('/test')
def test():
    """Тестовый API-маршрут"""
    return jsonify({'status': 'success', 'message': 'API работает'}) 