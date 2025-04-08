from flask import Blueprint, render_template

avito_bp = Blueprint('avito', __name__, url_prefix='/avito')

@avito_bp.route('/category/<category>')
def avito_category(category):
    return render_template('avito/category.html', category=category) 