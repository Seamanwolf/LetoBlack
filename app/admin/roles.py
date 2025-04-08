from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from werkzeug.security import generate_password_hash
from . import admin_bp
from app.utils import login_required, create_db_connection
from app.db.role_dao import RoleDAO
from flask_login import current_user

# Создаем экземпляр RoleDAO с конфигурацией БД из приложения
def get_role_dao():
    db_config = current_app.config.get('DB_CONFIG', {})
    return RoleDAO(db_config)

@admin_bp.route('/roles')
@login_required
def roles_list():
    """
    Страница со списком ролей
    """
    if not current_user.is_admin():
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('userlist.dashboard'))
        
    role_dao = get_role_dao()
    roles = role_dao.get_all_roles()
    
    return render_template(
        'admin/roles_list.html',
        roles=roles,
        active_page='roles'
    )

@admin_bp.route('/roles/create', methods=['GET', 'POST'])
@login_required
def role_create():
    """
    Страница создания новой роли
    """
    if not current_user.is_admin():
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('userlist.dashboard'))
    
    role_dao = get_role_dao()
    
    if request.method == 'POST':
        name = request.form.get('name')
        display_name = request.form.get('display_name')
        description = request.form.get('description')
        role_type = request.form.get('role_type', 'custom')
        
        # Проверка на существование роли с таким именем
        existing_role = role_dao.get_role_by_name(name)
        if existing_role:
            flash(f'Роль с именем "{name}" уже существует', 'danger')
            return render_template(
                'admin/role_form.html',
                role=None,
                is_new=True,
                active_page='roles'
            )
        
        # Создаем новую роль
        role_id = role_dao.create_role(name, display_name, description, role_type)
        
        if role_id:
            flash('Роль успешно создана', 'success')
            return redirect(url_for('admin.role_edit', role_id=role_id))
        else:
            flash('Ошибка при создании роли', 'danger')
    
    return render_template(
        'admin/role_form.html',
        role=None,
        is_new=True,
        active_page='roles'
    )

@admin_bp.route('/roles/edit/<int:role_id>', methods=['GET', 'POST'])
@login_required
def role_edit(role_id):
    """
    Страница редактирования роли
    """
    if not current_user.is_admin():
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('userlist.dashboard'))
    
    role_dao = get_role_dao()
    role = role_dao.get_role_by_id(role_id)
    
    if not role:
        flash('Роль не найдена', 'danger')
        return redirect(url_for('admin.roles_list'))
    
    # Получаем список всех модулей
    modules = role_dao.get_all_modules()
    
    # Получаем разрешения для роли
    permissions = role_dao.get_role_permissions(role_id)
    
    if request.method == 'POST':
        # Если роль системная, можно менять только описание
        if not role.get('is_system'):
            display_name = request.form.get('display_name')
            description = request.form.get('description')
            
            success = role_dao.update_role(role_id, display_name, description)
            
            if success:
                flash('Роль успешно обновлена', 'success')
            else:
                flash('Ошибка при обновлении роли', 'danger')
        
        # Обрабатываем изменения разрешений
        for module in modules:
            module_id = module['id']
            prefix = f'module_{module_id}_'
            
            can_view = request.form.get(f'{prefix}view') == 'on'
            can_create = request.form.get(f'{prefix}create') == 'on'
            can_edit = request.form.get(f'{prefix}edit') == 'on'
            can_delete = request.form.get(f'{prefix}delete') == 'on'
            
            role_dao.set_role_permissions(role_id, module_id, can_view, can_create, can_edit, can_delete)
        
        flash('Разрешения успешно обновлены', 'success')
        return redirect(url_for('admin.role_edit', role_id=role_id))
    
    return render_template(
        'admin/role_form.html',
        role=role,
        modules=modules,
        permissions=permissions,
        is_new=False,
        active_page='roles'
    )

@admin_bp.route('/roles/delete/<int:role_id>', methods=['POST'])
@login_required
def role_delete(role_id):
    """
    Удаление роли
    """
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'У вас нет доступа к этой операции'})
    
    role_dao = get_role_dao()
    role = role_dao.get_role_by_id(role_id)
    
    if not role:
        return jsonify({'success': False, 'message': 'Роль не найдена'})
    
    # Проверяем, что роль не системная
    if role.get('is_system'):
        return jsonify({'success': False, 'message': 'Системную роль удалить нельзя'})
    
    # Проверяем, что роль не используется пользователями
    users = role_dao.get_users_by_role(role_id)
    if users:
        return jsonify({
            'success': False, 
            'message': f'Роль используется {len(users)} пользователями. Переназначьте роль пользователям перед удалением.'
        })
    
    # Удаляем роль
    success = role_dao.delete_role(role_id)
    
    if success:
        return jsonify({'success': True, 'message': 'Роль успешно удалена'})
    else:
        return jsonify({'success': False, 'message': 'Ошибка при удалении роли'})

@admin_bp.route('/roles/users/<int:role_id>')
@login_required
def role_users(role_id):
    """
    Список пользователей с указанной ролью
    """
    if not current_user.is_admin():
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('userlist.dashboard'))
    
    role_dao = get_role_dao()
    role = role_dao.get_role_by_id(role_id)
    
    if not role:
        flash('Роль не найдена', 'danger')
        return redirect(url_for('admin.roles_list'))
    
    users = role_dao.get_users_by_role(role_id)
    
    return render_template(
        'admin/role_users.html',
        role=role,
        users=users,
        active_page='roles'
    ) 