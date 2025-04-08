#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import pymysql
import logging
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from datetime import datetime

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("migration.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('migration')

# Загружаем параметры подключения из переменных окружения
load_dotenv('config.env')

# Параметры подключения к старой базе данных
old_db_config = {
    'host': os.getenv('OLD_DB_HOST', '192.168.2.225'),
    'port': int(os.getenv('OLD_DB_PORT', 3306)),
    'user': os.getenv('OLD_DB_USER', 'test_user'),
    'password': os.getenv('OLD_DB_PASSWORD', 'password'),
    'database': os.getenv('OLD_DB_NAME', 'Brokers'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# Параметры подключения к новой базе данных
new_db_config = {
    'host': os.getenv('NEW_DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('NEW_DB_PORT', 3306)),
    'user': os.getenv('NEW_DB_USER', 'root'),
    'password': os.getenv('NEW_DB_PASSWORD', 'password'),
    'database': os.getenv('NEW_DB_NAME', 'Brokers_New'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_old_connection():
    """
    Создает соединение со старой базой данных
    """
    try:
        connection = pymysql.connect(**old_db_config)
        return connection
    except Exception as e:
        logger.error(f"Ошибка подключения к старой базе данных: {e}")
        return None

def get_new_connection():
    """
    Создает соединение с новой базой данных
    """
    try:
        connection = pymysql.connect(**new_db_config)
        return connection
    except Exception as e:
        logger.error(f"Ошибка подключения к новой базе данных: {e}")
        return None

def migrate_departments():
    """
    Мигрирует данные об отделах из старой базы в новую
    """
    logger.info("Миграция данных об отделах...")
    
    old_conn = get_old_connection()
    new_conn = get_new_connection()
    
    if not old_conn or not new_conn:
        return False
    
    try:
        # Получаем уникальные названия отделов из старой базы
        with old_conn.cursor() as old_cursor:
            old_cursor.execute("SELECT DISTINCT department FROM users WHERE department IS NOT NULL")
            departments = old_cursor.fetchall()
            
            if not departments:
                logger.warning("Отделы не найдены в старой базе данных")
                return False
            
            # Вставляем отделы в новую базу
            with new_conn.cursor() as new_cursor:
                # Сначала очищаем таблицу отделов в новой базе
                new_cursor.execute("TRUNCATE TABLE Departments")
                
                # Вставляем отделы
                for dept in departments:
                    department_name = dept['department']
                    if department_name and department_name.strip():
                        new_cursor.execute(
                            "INSERT INTO Departments (name, created_at) VALUES (%s, NOW())",
                            (department_name,)
                        )
                
                new_conn.commit()
                logger.info(f"Мигрировано {len(departments)} отделов")
                return True
    except Exception as e:
        logger.error(f"Ошибка миграции отделов: {e}")
        if new_conn:
            new_conn.rollback()
        return False
    finally:
        if old_conn:
            old_conn.close()
        if new_conn:
            new_conn.close()

def migrate_roles():
    """
    Мигрирует данные о ролях из старой базы в новую
    """
    logger.info("Миграция данных о ролях...")
    
    old_conn = get_old_connection()
    new_conn = get_new_connection()
    
    if not old_conn or not new_conn:
        return False
    
    try:
        # Получаем уникальные роли из старой базы
        with old_conn.cursor() as old_cursor:
            old_cursor.execute("SELECT DISTINCT role FROM users WHERE role IS NOT NULL")
            roles = old_cursor.fetchall()
            
            if not roles:
                logger.warning("Роли не найдены в старой базе данных")
                return False
            
            # Вставляем роли в новую базу
            with new_conn.cursor() as new_cursor:
                # Сначала очищаем таблицу ролей в новой базе
                new_cursor.execute("TRUNCATE TABLE Roles")
                
                # Маппинг для отображения внутренних названий ролей на отображаемые
                role_display_names = {
                    'admin': 'Администратор',
                    'leader': 'Руководитель',
                    'operator': 'Оператор',
                    'backoffice': 'Бэк-офис',
                    'user': 'Пользователь'
                }
                
                # Вставляем роли
                for role_item in roles:
                    role_name = role_item['role']
                    if role_name and role_name.strip():
                        display_name = role_display_names.get(role_name, role_name.capitalize())
                        new_cursor.execute(
                            "INSERT INTO Roles (name, display_name, created_at) VALUES (%s, %s, NOW())",
                            (role_name, display_name)
                        )
                
                new_conn.commit()
                logger.info(f"Мигрировано {len(roles)} ролей")
                return True
    except Exception as e:
        logger.error(f"Ошибка миграции ролей: {e}")
        if new_conn:
            new_conn.rollback()
        return False
    finally:
        if old_conn:
            old_conn.close()
        if new_conn:
            new_conn.close()

def migrate_users():
    """
    Мигрирует данные о пользователях из старой базы в новую
    """
    logger.info("Миграция данных о пользователях...")
    
    old_conn = get_old_connection()
    new_conn = get_new_connection()
    
    if not old_conn or not new_conn:
        return False
    
    try:
        # Получаем всех пользователей из старой базы
        with old_conn.cursor() as old_cursor:
            old_cursor.execute("SELECT * FROM users")
            users = old_cursor.fetchall()
            
            if not users:
                logger.warning("Пользователи не найдены в старой базе данных")
                return False
            
            # Получаем маппинги ID отделов и ролей из новой базы
            with new_conn.cursor() as new_cursor:
                # Получаем маппинг отделов
                new_cursor.execute("SELECT id, name FROM Departments")
                departments = {dept['name']: dept['id'] for dept in new_cursor.fetchall()}
                
                # Получаем маппинг ролей
                new_cursor.execute("SELECT id, name FROM Roles")
                roles = {role['name']: role['id'] for role in new_cursor.fetchall()}
                
                # Сначала очищаем таблицу пользователей в новой базе
                new_cursor.execute("TRUNCATE TABLE User")
                
                # Вставляем пользователей
                user_id_mapping = {}  # Для сохранения соответствия ID пользователей
                for user in users:
                    # Получаем ID отдела и роли из новой базы
                    department_id = departments.get(user.get('department')) if user.get('department') else None
                    role_id = roles.get(user.get('role')) if user.get('role') else roles.get('user')  # По умолчанию обычный пользователь
                    
                    # Если хэш пароля отсутствует, создаем новый
                    password_hash = user.get('password')
                    if not password_hash:
                        password_hash = generate_password_hash('password123')  # Временный пароль
                    
                    # Подготавливаем данные пользователя
                    new_user_data = {
                        'login': user.get('login'),
                        'password': password_hash,
                        'full_name': user.get('full_name'),
                        'department_id': department_id,
                        'role_id': role_id,
                        'position': user.get('position'),
                        'hired_date': user.get('hire_date'),
                        'fire_date': user.get('fire_date'),
                        'fired': user.get('fired', 0),
                        'personal_email': user.get('email'),
                        'pc_login': user.get('pc_login'),
                        'Phone': user.get('phone'),
                        'office': user.get('office'),
                        'corp_phone': user.get('corp_phone'),
                        'created_at': datetime.now()
                    }
                    
                    # Строим SQL запрос динамически, исключая None значения
                    fields = []
                    values = []
                    placeholders = []
                    
                    for key, value in new_user_data.items():
                        if value is not None:
                            fields.append(key)
                            values.append(value)
                            placeholders.append('%s')
                    
                    sql = f"INSERT INTO User ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
                    new_cursor.execute(sql, values)
                    
                    # Сохраняем соответствие ID
                    old_id = user.get('id')
                    new_id = new_cursor.lastrowid
                    user_id_mapping[old_id] = new_id
                
                new_conn.commit()
                logger.info(f"Мигрировано {len(users)} пользователей")
                
                # Сохраняем маппинг ID пользователей в файл
                with open('user_id_mapping.txt', 'w') as f:
                    for old_id, new_id in user_id_mapping.items():
                        f.write(f"{old_id},{new_id}\n")
                
                return user_id_mapping
    except Exception as e:
        logger.error(f"Ошибка миграции пользователей: {e}")
        if new_conn:
            new_conn.rollback()
        return False
    finally:
        if old_conn:
            old_conn.close()
        if new_conn:
            new_conn.close()

def migrate_call_center_settings(user_id_mapping):
    """
    Мигрирует настройки колл-центра из старой базы в новую
    """
    logger.info("Миграция настроек колл-центра...")
    
    if not user_id_mapping:
        logger.error("Отсутствует маппинг ID пользователей")
        return False
    
    old_conn = get_old_connection()
    new_conn = get_new_connection()
    
    if not old_conn or not new_conn:
        return False
    
    try:
        # Получаем настройки колл-центра из старой базы
        with old_conn.cursor() as old_cursor:
            old_cursor.execute("SELECT * FROM users WHERE ukc_kc IS NOT NULL AND ukc_kc != ''")
            operators = old_cursor.fetchall()
            
            if not operators:
                logger.warning("Настройки колл-центра не найдены в старой базе данных")
                return False
            
            # Вставляем настройки в новую базу
            with new_conn.cursor() as new_cursor:
                # Сначала очищаем таблицу настроек в новой базе
                new_cursor.execute("TRUNCATE TABLE CallCenterSettings")
                
                # Вставляем настройки
                for operator in operators:
                    old_id = operator.get('id')
                    if old_id in user_id_mapping:
                        new_id = user_id_mapping[old_id]
                        new_cursor.execute(
                            "INSERT INTO CallCenterSettings (user_id, ukc_kc, created_at) VALUES (%s, %s, NOW())",
                            (new_id, operator.get('ukc_kc'))
                        )
                
                new_conn.commit()
                logger.info(f"Мигрировано {len(operators)} настроек колл-центра")
                return True
    except Exception as e:
        logger.error(f"Ошибка миграции настроек колл-центра: {e}")
        if new_conn:
            new_conn.rollback()
        return False
    finally:
        if old_conn:
            old_conn.close()
        if new_conn:
            new_conn.close()

def migrate_user_activity(user_id_mapping):
    """
    Мигрирует данные о статусах активности пользователей
    """
    logger.info("Миграция статусов активности пользователей...")
    
    if not user_id_mapping:
        logger.error("Отсутствует маппинг ID пользователей")
        return False
    
    old_conn = get_old_connection()
    new_conn = get_new_connection()
    
    if not old_conn or not new_conn:
        return False
    
    try:
        # В старой базе нет отдельной таблицы для статусов активности,
        # поэтому просто создаем записи по умолчанию для всех пользователей
        with new_conn.cursor() as new_cursor:
            # Сначала очищаем таблицу активности в новой базе
            new_cursor.execute("TRUNCATE TABLE UserActivity")
            
            # Вставляем статусы активности
            for old_id, new_id in user_id_mapping.items():
                new_cursor.execute(
                    "INSERT INTO UserActivity (user_id, status, last_activity, created_at) VALUES (%s, %s, NOW(), NOW())",
                    (new_id, 'offline')
                )
            
            new_conn.commit()
            logger.info(f"Создано {len(user_id_mapping)} записей статусов активности")
            return True
    except Exception as e:
        logger.error(f"Ошибка миграции статусов активности: {e}")
        if new_conn:
            new_conn.rollback()
        return False
    finally:
        if old_conn:
            old_conn.close()
        if new_conn:
            new_conn.close()

def run_migration():
    """
    Запускает полный процесс миграции
    """
    logger.info("Начало процесса миграции данных...")
    
    # 1. Миграция отделов
    if not migrate_departments():
        logger.error("Миграция отделов не выполнена. Процесс миграции прерван.")
        return False
    
    # 2. Миграция ролей
    if not migrate_roles():
        logger.error("Миграция ролей не выполнена. Процесс миграции прерван.")
        return False
    
    # 3. Миграция пользователей
    user_id_mapping = migrate_users()
    if not user_id_mapping:
        logger.error("Миграция пользователей не выполнена. Процесс миграции прерван.")
        return False
    
    # 4. Миграция настроек колл-центра
    if not migrate_call_center_settings(user_id_mapping):
        logger.warning("Миграция настроек колл-центра не выполнена.")
    
    # 5. Миграция статусов активности
    if not migrate_user_activity(user_id_mapping):
        logger.warning("Миграция статусов активности не выполнена.")
    
    logger.info("Процесс миграции данных успешно завершен.")
    return True

if __name__ == "__main__":
    run_migration()