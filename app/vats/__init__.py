from flask import Blueprint, render_template

vats_bp = Blueprint('vats', __name__, url_prefix='/admin/vats', template_folder='../templates/admin/vats')

@vats_bp.route('/')
def index():
    # Пример данных - заменить на реальные из БД
    data = {
        'total_numbers': 100,
        'assigned_numbers': 70,
        'free_numbers': 30,
        'changed_week': 15,
        'numbers': [
            {'phone': '+7(123)456-78-90', 'status': 'Назначен', 'employee': 'Иванов И.И.', 'assigned_at': '2023-10-01'},
            {'phone': '+7(987)654-32-10', 'status': 'Свободен', 'employee': None, 'assigned_at': None}
        ]
    }
    return render_template('index.html', **data) 