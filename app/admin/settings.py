from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from . import admin_bp
from app.utils import login_required, create_db_connection
from app.db.role_dao import RoleDAO
from flask_login import current_user

# Создаем экземпляр RoleDAO с конфигурацией БД из приложения
def get_role_dao():
    db_config = current_app.config.get('DB_CONFIG', {})
    return RoleDAO(db_config)

@admin_bp.route('/settings')
@login_required
def settings():
    """
    Страница настроек системы
    """
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('userlist.dashboard'))
    
    return render_template(
        'admin/settings.html',
        active_page='settings',
        active_tab='general'
    )

@admin_bp.route('/settings/roles')
@login_required
def settings_roles():
    """
    Раздел настроек для управления ролями пользователей
    """
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('userlist.dashboard'))
    
    role_dao = get_role_dao()
    roles = role_dao.get_all_roles()
    
    return render_template(
        'admin/settings_roles.html',
        roles=roles,
        active_page='settings',
        active_tab='roles'
    )

@admin_bp.route('/settings/add_role', methods=['POST'])
@login_required
def add_role():
    """
    Обработчик для добавления новой роли
    """
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой операции', 'danger')
        return redirect(url_for('userlist.dashboard'))
    
    name = request.form.get('name')
    display_name = request.form.get('display_name')
    role_type = request.form.get('role_type')
    description = request.form.get('description')
    
    # Проверка обязательных полей
    if not name or not display_name:
        flash('Имя и отображаемое имя обязательны для заполнения', 'danger')
        return redirect(url_for('admin.settings_roles'))
    
    # Проверка корректности имени (только латинские буквы, цифры и подчеркивания)
    import re
    if not re.match(r'^[a-z0-9_]+$', name):
        flash('Системное имя может содержать только латинские буквы в нижнем регистре, цифры и подчеркивания', 'danger')
        return redirect(url_for('admin.settings_roles'))
    
    role_dao = get_role_dao()
    
    # Проверка на существование роли с таким именем
    existing_role = role_dao.get_role_by_name(name)
    if existing_role:
        flash(f'Роль с именем "{name}" уже существует', 'danger')
        return redirect(url_for('admin.settings_roles'))
    
    # Создаем новую роль
    role_id = role_dao.create_role(name, display_name, role_type, description)
    
    if role_id:
        flash('Роль успешно создана', 'success')
    else:
        flash('Ошибка при создании роли', 'danger')
    
    return redirect(url_for('admin.settings_roles'))

@admin_bp.route('/settings/update_role', methods=['POST'])
@login_required
def update_role():
    """
    Обработчик для обновления роли
    """
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой операции', 'danger')
        return redirect(url_for('userlist.dashboard'))
    
    role_id = request.form.get('role_id')
    display_name = request.form.get('display_name')
    role_type = request.form.get('role_type')
    description = request.form.get('description')
    
    # Проверка обязательных полей
    if not role_id or not display_name:
        flash('ID роли и отображаемое имя обязательны для заполнения', 'danger')
        return redirect(url_for('admin.settings_roles'))
    
    role_dao = get_role_dao()
    
    # Проверка существования роли
    role = role_dao.get_role_by_id(role_id)
    if not role:
        flash('Роль не найдена', 'danger')
        return redirect(url_for('admin.settings_roles'))
    
    # Обновляем роль
    success = role_dao.update_role(int(role_id), display_name, role_type, description)
    
    if success:
        flash('Роль успешно обновлена', 'success')
    else:
        flash('Ошибка при обновлении роли', 'danger')
    
    return redirect(url_for('admin.settings_roles'))

@admin_bp.route('/settings/delete_role', methods=['POST'])
@login_required
def delete_role():
    """
    Обработчик для удаления роли
    """
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой операции', 'danger')
        return redirect(url_for('userlist.dashboard'))
    
    role_id = request.form.get('role_id')
    
    if not role_id:
        flash('ID роли обязателен для заполнения', 'danger')
        return redirect(url_for('admin.settings_roles'))
    
    role_dao = get_role_dao()
    
    # Проверка существования роли
    role = role_dao.get_role_by_id(role_id)
    if not role:
        flash('Роль не найдена', 'danger')
        return redirect(url_for('admin.settings_roles'))
    
    # Проверка, что роль не системная
    if role.is_system:
        flash('Системные роли нельзя удалить', 'danger')
        return redirect(url_for('admin.settings_roles'))
    
    # Проверка на наличие пользователей с этой ролью
    users = role_dao.get_users_by_role_id(role_id)
    if users:
        flash(f'Невозможно удалить роль, так как она назначена {len(users)} пользователям', 'danger')
        return redirect(url_for('admin.settings_roles'))
    
    # Удаляем роль
    success = role_dao.delete_role(int(role_id))
    
    if success:
        flash('Роль успешно удалена', 'success')
    else:
        flash('Ошибка при удалении роли', 'danger')
    
    return redirect(url_for('admin.settings_roles'))

@admin_bp.route('/settings/get_modules', methods=['GET'])
@login_required
def get_modules():
    """
    API для получения списка всех модулей
    """
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Доступ запрещен'})
    
    role_dao = get_role_dao()
    modules = role_dao.get_all_modules()
    
    return jsonify({'success': True, 'modules': modules})

@admin_bp.route('/settings/get_role_permissions/<int:role_id>', methods=['GET'])
@login_required
def get_role_permissions(role_id):
    """
    API для получения разрешений роли
    """
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Доступ запрещен'})
    
    role_dao = get_role_dao()
    
    # Проверка существования роли
    role = role_dao.get_role_by_id(role_id)
    if not role:
        return jsonify({'success': False, 'message': 'Роль не найдена'})
    
    # Получаем разрешения роли
    permissions = role_dao.get_role_permissions(role_id)
    
    return jsonify({'success': True, 'permissions': permissions})

@admin_bp.route('/settings/update_role_permissions', methods=['POST'])
@login_required
def update_role_permissions():
    """
    Обработчик для обновления разрешений роли
    """
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой операции', 'danger')
        return redirect(url_for('userlist.dashboard'))
    
    role_id = request.form.get('role_id')
    
    if not role_id:
        flash('ID роли обязателен для заполнения', 'danger')
        return redirect(url_for('admin.settings_roles'))
    
    role_dao = get_role_dao()
    
    # Проверка существования роли
    role = role_dao.get_role_by_id(role_id)
    if not role:
        flash('Роль не найдена', 'danger')
        return redirect(url_for('admin.settings_roles'))
    
    # Получаем все модули
    modules = role_dao.get_all_modules()
    
    # Очищаем текущие разрешения роли
    if not role.is_system:
        role_dao.clear_role_permissions(int(role_id))
    
    # Обрабатываем новые разрешения для каждого модуля
    for module in modules:
        module_id = module['id']
        module_name = module['name']
        
        # Получаем значения чекбоксов для каждого действия
        can_view = request.form.get(f'perm_{module_name}_view') == 'on'
        can_create = request.form.get(f'perm_{module_name}_create') == 'on'
        can_edit = request.form.get(f'perm_{module_name}_edit') == 'on'
        can_delete = request.form.get(f'perm_{module_name}_delete') == 'on'
        
        # Если хотя бы одно разрешение выбрано, устанавливаем его
        if can_view or can_create or can_edit or can_delete:
            role_dao.set_role_permissions(int(role_id), module_id, can_view, can_create, can_edit, can_delete)
    
    flash('Разрешения роли успешно обновлены', 'success')
    return redirect(url_for('admin.settings_roles')) 