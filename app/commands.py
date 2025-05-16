import click
from flask.cli import with_appcontext
from app import db
from app.models.role import Role
from app.models.permission import Permission
from app.models.system_module import SystemModule
from app.models import User
import os
from app.utils import execute_sql_file
import logging

logger = logging.getLogger(__name__)

@click.command('init-roles')
@with_appcontext
def init_roles_command():
    """Инициализирует базовые роли и модули системы."""
    # Создаем основные модули системы
    modules = [
        {
            'name': 'dashboard',
            'display_name': 'Дашборд',
            'description': 'Общий обзор системы',
            'icon': 'fas fa-tachometer-alt',
            'order': 1
        },
        {
            'name': 'users',
            'display_name': 'Пользователи',
            'description': 'Управление пользователями системы',
            'icon': 'fas fa-users',
            'order': 2
        },
        {
            'name': 'roles',
            'display_name': 'Роли',
            'description': 'Управление ролями и разрешениями',
            'icon': 'fas fa-user-tag',
            'order': 3
        },
        {
            'name': 'settings',
            'display_name': 'Настройки',
            'description': 'Общие настройки системы',
            'icon': 'fas fa-cogs',
            'order': 10
        },
        {
            'name': 'logs',
            'display_name': 'Логи',
            'description': 'Просмотр системных журналов',
            'icon': 'fas fa-clipboard-list',
            'order': 11
        }
    ]
    
    click.echo('Создание модулей системы...')
    created_modules = []
    for module_data in modules:
        module = SystemModule.get_or_create(
            name=module_data['name'],
            display_name=module_data['display_name'],
            description=module_data['description'],
            icon=module_data['icon'],
            order=module_data['order']
        )
        created_modules.append(module)
        click.echo(f'Модуль {module.display_name} создан или уже существует')
    
    # Создаем системные роли
    roles = [
        {
            'name': 'admin',
            'display_name': 'Администратор',
            'description': 'Полный доступ ко всем возможностям системы',
            'type': 'system',
            'is_system': True
        },
        {
            'name': 'leader',
            'display_name': 'Руководитель',
            'description': 'Доступ к управлению и мониторингу',
            'type': 'system',
            'is_system': True
        },
        {
            'name': 'operator',
            'display_name': 'Оператор',
            'description': 'Базовые операции в системе',
            'type': 'system',
            'is_system': True
        },
        {
            'name': 'user',
            'display_name': 'Пользователь',
            'description': 'Обычный пользователь с минимальными правами',
            'type': 'system',
            'is_system': True
        },
        {
            'name': 'backoffice',
            'display_name': 'Бэк-офис',
            'description': 'Доступ к административным функциям',
            'type': 'backoffice',
            'is_system': False
        }
    ]
    
    click.echo('Создание системных ролей...')
    created_roles = {}
    
    for role_data in roles:
        role = Role.get_by_name(role_data['name'])
        
        if role is None:
            role = Role(
                name=role_data['name'],
                display_name=role_data['display_name'],
                description=role_data['description'],
                role_type=role_data['type'],
                is_system=role_data['is_system']
            )
            role.save()
            click.echo(f"Роль {role.display_name} создана")
        else:
            click.echo(f"Роль {role.display_name} уже существует")
            
        created_roles[role_data['name']] = role
    
    # Назначаем разрешения для ролей
    click.echo('Назначение разрешений для ролей...')
    
    # Администратор получает все права на все модули
    admin_role = created_roles.get('admin')
    if admin_role:
        admin_permissions = []
        for module in created_modules:
            permission = Permission.get_or_create(
                module_name=module.name,
                can_view=True,
                can_create=True,
                can_edit=True,
                can_delete=True
            )
            admin_permissions.append(permission.id)
        
        admin_role.update_permissions(admin_permissions)
        click.echo('Разрешения для администратора настроены')
    
    # Руководитель получает права на просмотр всех модулей и редактирование некоторых
    leader_role = created_roles.get('leader')
    if leader_role:
        leader_permissions = []
        for module in created_modules:
            can_edit = module.name in ['dashboard', 'users']
            can_create = module.name in ['users']
            can_delete = module.name in ['users']
            
            permission = Permission.get_or_create(
                module_name=module.name,
                can_view=True,
                can_create=can_create,
                can_edit=can_edit,
                can_delete=can_delete
            )
            leader_permissions.append(permission.id)
        
        leader_role.update_permissions(leader_permissions)
        click.echo('Разрешения для руководителя настроены')
    
    # Оператор получает права на просмотр большинства модулей
    operator_role = created_roles.get('operator')
    if operator_role:
        operator_permissions = []
        for module in created_modules:
            if module.name not in ['roles', 'settings', 'logs']:
                permission = Permission.get_or_create(
                    module_name=module.name,
                    can_view=True,
                    can_create=False,
                    can_edit=False,
                    can_delete=False
                )
                operator_permissions.append(permission.id)
        
        operator_role.update_permissions(operator_permissions)
        click.echo('Разрешения для оператора настроены')
    
    # Обычный пользователь получает права только на просмотр дашборда
    user_role = created_roles.get('user')
    if user_role:
        permission = Permission.get_or_create(
            module_name='dashboard',
            can_view=True,
            can_create=False,
            can_edit=False,
            can_delete=False
        )
        user_role.update_permissions([permission.id])
        click.echo('Разрешения для пользователя настроены')
    
    # Проверяем, есть ли админ в системе
    admin_user = User.get_by_username('admin')
    if not admin_user:
        click.echo('Создание пользователя admin...')
        admin_user = User(
            username='admin',
            email='admin@example.com',
            password='admin123',
            first_name='Admin',
            last_name='User'
        )
        admin_user.save()
        
        # Назначаем роль администратора
        admin_user.add_role(admin_role.id)
        click.echo('Пользователь admin создан и назначена роль администратора')
    else:
        click.echo('Пользователь admin уже существует')
        # Проверяем, есть ли у админа роль администратора
        if not admin_user.has_role('admin'):
            admin_user.add_role(admin_role.id)
            click.echo('Пользователю admin назначена роль администратора')
            
    click.echo('Инициализация ролей и модулей завершена успешно!')

@click.command('create-org-tables')
@with_appcontext
def create_org_tables_command():
    """Создает таблицы организационной структуры."""
    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'sql')
    
    # Список SQL-файлов в порядке выполнения
    sql_files = [
        'create_position_table.sql',
        'create_location_table.sql',
        'create_department_table.sql',
        'create_employee_table.sql',
        'add_department_leader_fk.sql'
    ]
    
    success = True
    for sql_file in sql_files:
        file_path = os.path.join(base_dir, sql_file)
        logger.info(f"Выполнение SQL-файла: {file_path}")
        logger.info(f"Файл существует: {os.path.exists(file_path)}")
        
        if os.path.exists(file_path):
            result = execute_sql_file(file_path)
            logger.info(f"Результат выполнения SQL-файла {sql_file}: {result}")
            if not result:
                success = False
                click.echo(f"Ошибка при выполнении SQL-файла {sql_file}")
        else:
            success = False
            click.echo(f"SQL-файл не найден: {file_path}")
    
    if success:
        click.echo('Таблицы организационной структуры успешно созданы.')
    else:
        click.echo('Произошла ошибка при создании таблиц организационной структуры.')

def init_app(app):
    """Регистрирует CLI команды."""
    app.cli.add_command(init_roles_command)
    app.cli.add_command(create_org_tables_command) 