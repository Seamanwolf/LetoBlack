from flask import render_template
from flask_login import login_required
from . import news_bp

@news_bp.route('/')
@login_required
def index():
    """Отображает страницу с новостями"""
    return render_template('news/index.html') 