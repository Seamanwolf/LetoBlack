from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from . import admin_bp
from app.utils import login_required, create_db_connection, admin_required, validate_role_form, validate_update_role_form, logger
from app.db.role_dao import RoleDAO
from flask_login import current_user
import traceback
from app.services.permissions_service import PermissionService
from app.services.audit_service import AuditService
import json

# Создаем экземпляр RoleDAO с конфигурацией БД из приложения
def get_role_dao():
    db_config = current_app.config.get('DB_CONFIG', {})
    return RoleDAO(db_config)

@admin_bp.route('/settings')
@login_required
@admin_required
def settings():
    """
    Страница настроек системы
    """
    return render_template(
        'admin/settings.html',
        active_page='settings',
        active_tab='general'
    )

@admin_bp.route('/settings/roles')
@login_required
@admin_required
def settings_roles():
    """
    Раздел настроек для управления ролями пользователей
    """
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
@admin_required
def add_role():
    """
    Обработчик для добавления новой роли
    """
    is_valid, error_message = validate_role_form(request.form)
    if not is_valid:
        flash(error_message, 'danger')
        AuditService.log_user_action(current_user, 'create_role', 'role', None, error_message, 'fail', request.remote_addr)
        return redirect(url_for('admin.settings_roles'))
    name = request.form.get('name')
    display_name = request.form.get('display_name')
    role_type = request.form.get('role_type')
    description = request.form.get('description')
    try:
    role_dao = get_role_dao()
    existing_role = role_dao.get_role_by_name(name)
    if existing_role:
        flash(f'Роль с именем "{name}" уже существует', 'danger')
            AuditService.log_user_action(current_user, 'create_role', 'role', None, f'Role name exists: {name}', 'fail', request.remote_addr)
        return redirect(url_for('admin.settings_roles'))
    role_id = role_dao.create_role(name, display_name, role_type, description)
    if role_id:
        flash('Роль успешно создана', 'success')
            AuditService.log_user_action(current_user, 'create_role', 'role', role_id, json.dumps({'name': name, 'display_name': display_name, 'role_type': role_type, 'description': description}), 'success', request.remote_addr)
    else:
        flash('Ошибка при создании роли', 'danger')
            AuditService.log_user_action(current_user, 'create_role', 'role', None, 'DB error', 'fail', request.remote_addr)
    except Exception as e:
        logger.error(f"Ошибка при создании роли: {e}\n{traceback.format_exc()}")
        flash('Произошла ошибка при создании роли', 'danger')
        AuditService.log_user_action(current_user, 'create_role', 'role', None, str(e), 'error', request.remote_addr)
    return redirect(url_for('admin.settings_roles'))

@admin_bp.route('/settings/update_role', methods=['POST'])
@login_required
@admin_required
def update_role():
    """
    Обработчик для обновления роли
    """
    is_valid, error_message = validate_update_role_form(request.form)
    if not is_valid:
        flash(error_message, 'danger')
        AuditService.log_user_action(current_user, 'update_role', 'role', request.form.get('role_id'), error_message, 'fail', request.remote_addr)
        return redirect(url_for('admin.settings_roles'))
    role_id = request.form.get('role_id')
    display_name = request.form.get('display_name')
    role_type = request.form.get('role_type')
    description = request.form.get('description')
    try:
    role_dao = get_role_dao()
    role = role_dao.get_role_by_id(role_id)
    if not role:
        flash('Роль не найдена', 'danger')
            AuditService.log_user_action(current_user, 'update_role', 'role', role_id, 'Role not found', 'fail', request.remote_addr)
        return redirect(url_for('admin.settings_roles'))
    success = role_dao.update_role(int(role_id), display_name, role_type, description)
    if success:
        flash('Роль успешно обновлена', 'success')
            AuditService.log_user_action(current_user, 'update_role', 'role', role_id, json.dumps({'display_name': display_name, 'role_type': role_type, 'description': description}), 'success', request.remote_addr)
    else:
        flash('Ошибка при обновлении роли', 'danger')
            AuditService.log_user_action(current_user, 'update_role', 'role', role_id, 'DB error', 'fail', request.remote_addr)
    except Exception as e:
        logger.error(f"Ошибка при обновлении роли: {e}\n{traceback.format_exc()}")
        flash('Произошла ошибка при обновлении роли', 'danger')
        AuditService.log_user_action(current_user, 'update_role', 'role', role_id, str(e), 'error', request.remote_addr)
    return redirect(url_for('admin.settings_roles'))

@admin_bp.route('/settings/delete_role', methods=['POST'])
@login_required
@admin_required
def delete_role():
    """
    Обработчик для удаления роли
    """
    role_id = request.form.get('role_id')
    try:
    role_dao = get_role_dao()
    role = role_dao.get_role_by_id(role_id)
    if not role:
        flash('Роль не найдена', 'danger')
            AuditService.log_user_action(current_user, 'delete_role', 'role', role_id, 'Role not found', 'fail', request.remote_addr)
        return redirect(url_for('admin.settings_roles'))
    if role.is_system:
        flash('Системные роли нельзя удалить', 'danger')
            AuditService.log_user_action(current_user, 'delete_role', 'role', role_id, 'System role', 'fail', request.remote_addr)
        return redirect(url_for('admin.settings_roles'))
    users = role_dao.get_users_by_role_id(role_id)
    if users:
        flash(f'Невозможно удалить роль, так как она назначена {len(users)} пользователям', 'danger')
            AuditService.log_user_action(current_user, 'delete_role', 'role', role_id, f'Role assigned to {len(users)} users', 'fail', request.remote_addr)
        return redirect(url_for('admin.settings_roles'))
    success = role_dao.delete_role(int(role_id))
    if success:
        flash('Роль успешно удалена', 'success')
            AuditService.log_user_action(current_user, 'delete_role', 'role', role_id, None, 'success', request.remote_addr)
    else:
        flash('Ошибка при удалении роли', 'danger')
            AuditService.log_user_action(current_user, 'delete_role', 'role', role_id, 'DB error', 'fail', request.remote_addr)
    except Exception as e:
        logger.error(f"Ошибка при удалении роли: {e}\n{traceback.format_exc()}")
        flash('Произошла ошибка при удалении роли', 'danger')
        AuditService.log_user_action(current_user, 'delete_role', 'role', role_id, str(e), 'error', request.remote_addr)
    return redirect(url_for('admin.settings_roles'))

@admin_bp.route('/settings/get_modules', methods=['GET'])
@login_required
@admin_required
def get_modules():
    """
    API для получения списка всех модулей
    """
    service = PermissionService()
    modules = service.get_all_modules()
    return jsonify({'success': True, 'modules': modules})

@admin_bp.route('/settings/get_role_permissions/<int:role_id>', methods=['GET'])
@login_required
@admin_required
def get_role_permissions(role_id):
    """
    API для получения разрешений роли
    """
    service = PermissionService()
    role_dao = get_role_dao()
    # Проверка существования роли
    role = role_dao.get_role_by_id(role_id)
    if not role:
        return jsonify({'success': False, 'message': 'Роль не найдена'})
    # Получаем разрешения роли
    permissions = service.get_role_permissions(role_id)
    return jsonify({'success': True, 'permissions': permissions})

@admin_bp.route('/settings/update_role_permissions', methods=['POST'])
@login_required
@admin_required
def update_role_permissions():
    """
    Обработчик для обновления разрешений роли
    """
    role_id = request.form.get('role_id')
    if not role_id:
        flash('ID роли обязателен для заполнения', 'danger')
        AuditService.log_user_action(current_user, 'update_role_permissions', 'role', None, 'No role_id', 'fail', request.remote_addr)
        return redirect(url_for('admin.settings_roles'))
    service = PermissionService()
    role_dao = get_role_dao()
    try:
    role = role_dao.get_role_by_id(role_id)
    if not role:
        flash('Роль не найдена', 'danger')
            AuditService.log_user_action(current_user, 'update_role_permissions', 'role', role_id, 'Role not found', 'fail', request.remote_addr)
        return redirect(url_for('admin.settings_roles'))
        modules = service.get_all_modules()
    if not role.is_system:
            service.clear_role_permissions(int(role_id))
        changed = []
    for module in modules:
        module_id = module['id']
        module_name = module['name']
        can_view = request.form.get(f'perm_{module_name}_view') == 'on'
        can_create = request.form.get(f'perm_{module_name}_create') == 'on'
        can_edit = request.form.get(f'perm_{module_name}_edit') == 'on'
        can_delete = request.form.get(f'perm_{module_name}_delete') == 'on'
        if can_view or can_create or can_edit or can_delete:
                service.set_role_permissions(int(role_id), module_id, can_view, can_create, can_edit, can_delete)
                changed.append({
                    'module_id': module_id,
                    'can_view': can_view,
                    'can_create': can_create,
                    'can_edit': can_edit,
                    'can_delete': can_delete
                })
    flash('Разрешения роли успешно обновлены', 'success')
        AuditService.log_user_action(current_user, 'update_role_permissions', 'role', role_id, json.dumps(changed), 'success', request.remote_addr)
    except Exception as e:
        logger.error(f"Ошибка при обновлении разрешений роли: {e}\n{traceback.format_exc()}")
        flash('Произошла ошибка при обновлении разрешений', 'danger')
        AuditService.log_user_action(current_user, 'update_role_permissions', 'role', role_id, str(e), 'error', request.remote_addr)
    return redirect(url_for('admin.settings_roles')) 

@admin_bp.route('/settings/logs')
@login_required
@admin_required
def settings_logs():
    """
    Страница просмотра логов действий пользователей с фильтрами
    """
    from app.models.audit_log import AuditLog
    from flask import request
    # Получаем фильтры из query-параметров
    username = request.args.get('username')
    action = request.args.get('action')
    status = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    # Формируем SQL-запрос с учётом фильтров
    sql = 'SELECT * FROM audit_log WHERE 1=1'
    params = []
    if username:
        sql += ' AND username LIKE %s'
        params.append(f'%{username}%')
    if action:
        sql += ' AND action = %s'
        params.append(action)
    if status:
        sql += ' AND status = %s'
        params.append(status)
    if date_from:
        sql += ' AND timestamp >= %s'
        params.append(date_from)
    if date_to:
        sql += ' AND timestamp <= %s'
        params.append(date_to)
    sql += ' ORDER BY timestamp DESC LIMIT 200'
    conn = None
    logs = []
    try:
        from app.db_connection import create_db_connection
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        logs = cursor.fetchall()
        cursor.close()
    finally:
        if conn:
            conn.close()
    # Для фильтров actions/status можно получить уникальные значения
    actions = set([log['action'] for log in logs])
    statuses = set([log['status'] for log in logs])
    return render_template(
        'admin/settings_logs.html',
        logs=logs,
        actions=actions,
        statuses=statuses,
        active_page='settings',
        active_tab='logs',
        filters={'username': username, 'action': action, 'status': status, 'date_from': date_from, 'date_to': date_to}
    ) 