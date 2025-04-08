from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.models.role import Role
from app.models.permission import Permission
from app.models.system_module import SystemModule
from app.decorators import admin_required

roles_bp = Blueprint('roles', __name__, url_prefix='/admin/settings/roles')

@roles_bp.route('/', methods=['GET'])
@roles_bp.route('/list', methods=['GET'])
@login_required
@admin_required
def index():
    """Отображает страницу управления ролями"""
    roles = Role.get_all()
    return render_template('admin/settings/roles.html', roles=roles)

@roles_bp.route('/add', methods=['POST'])
@login_required
@admin_required
def add_role():
    """Добавляет новую роль"""
    name = request.form.get('name')
    display_name = request.form.get('display_name')
    description = request.form.get('description')
    role_type = request.form.get('role_type', 'custom')
    
    # Проверка существования роли с таким именем
    existing_role = Role.get_by_name(name)
    if existing_role:
        flash('Роль с таким именем уже существует', 'danger')
        return redirect(url_for('admin.settings', tab='roles'))
    
    # Создаем новую роль
    new_role = Role(
        name=name,
        display_name=display_name,
        description=description,
        role_type=role_type,
        is_system=False
    )
    
    new_role.save()
    
    flash(f'Роль "{display_name}" успешно создана', 'success')
    return redirect(url_for('admin.settings', tab='roles'))

@roles_bp.route('/update', methods=['POST'])
@login_required
@admin_required
def update_role():
    """Обновляет существующую роль"""
    role_id = request.form.get('role_id')
    display_name = request.form.get('display_name')
    description = request.form.get('description')
    role_type = request.form.get('role_type')
    
    role = Role.get_by_id(role_id)
    if not role:
        flash('Роль не найдена', 'danger')
        return redirect(url_for('admin.settings', tab='roles'))
    
    # Проверка, что системную роль нельзя изменить
    if role.is_system:
        # Для системных ролей можно менять только описание
        role.description = description
    else:
        # Для обычных ролей можно менять всё
        role.display_name = display_name
        role.description = description
        role.type = role_type
    
    role.save()
    
    flash(f'Роль "{role.display_name}" успешно обновлена', 'success')
    return redirect(url_for('admin.settings', tab='roles'))

@roles_bp.route('/delete', methods=['POST'])
@login_required
@admin_required
def delete_role():
    """Удаляет роль"""
    role_id = request.form.get('role_id')
    
    role = Role.get_by_id(role_id)
    if not role:
        flash('Роль не найдена', 'danger')
        return redirect(url_for('admin.settings', tab='roles'))
    
    # Проверка, что системную роль нельзя удалить
    if role.is_system:
        flash('Системные роли нельзя удалить', 'danger')
        return redirect(url_for('admin.settings', tab='roles'))
    
    # Проверка наличия пользователей с этой ролью
    # Эту проверку нужно будет реализовать в модели User
    
    try:
        role.delete()
        flash(f'Роль "{role.display_name}" успешно удалена', 'success')
    except Exception as e:
        flash(f'Ошибка при удалении роли: {str(e)}', 'danger')
    
    return redirect(url_for('admin.settings', tab='roles'))

@roles_bp.route('/get_role_permissions/<int:role_id>', methods=['GET'])
@login_required
@admin_required
def get_role_permissions(role_id):
    """Получает права доступа для роли"""
    role = Role.get_by_id(role_id)
    if not role:
        return jsonify({'error': 'Роль не найдена'}), 404
    
    permissions = role.get_permissions()
    return jsonify({
        'role_id': role.id,
        'permissions': [p.to_dict() for p in permissions]
    })

@roles_bp.route('/get_modules', methods=['GET'])
@login_required
@admin_required
def get_modules():
    """Получает список модулей системы"""
    modules = SystemModule.get_all()
    return jsonify({
        'modules': [m.to_dict() for m in modules]
    })

@roles_bp.route('/update_role_permissions', methods=['POST'])
@login_required
@admin_required
def update_role_permissions():
    """Обновляет права доступа для роли"""
    role_id = request.form.get('role_id')
    permission_ids = request.form.getlist('permissions[]')
    
    role = Role.get_by_id(role_id)
    if not role:
        return jsonify({'error': 'Роль не найдена'}), 404
    
    try:
        role.update_permissions(permission_ids)
        return jsonify({'message': 'Права доступа успешно обновлены'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500 