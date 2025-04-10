#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pymysql
import hashlib
import secrets
import os
import configparser
import logging
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv('config.env')

def create_db_connection():
    """Создание подключения к базе данных"""
    # Стандартные параметры подключения
    db_config = {
        'host': '192.168.2.225',
        'port': 3306,
        'user': 'test_user',
        'password': 'password',
        'database': 'Brokers',
        'cursorclass': pymysql.cursors.DictCursor
    }

    try:
        connection = pymysql.connect(**db_config)
        print("Подключение к базе данных установлено успешно.")
        return connection
    except Exception as e:
        print(f"Ошибка при подключении к базе данных: {e}")
        return None

def create_test_role():
    """Создание тестовой роли с доступом к базовым модулям"""
    connection = create_db_connection()
    if not connection:
        print("Не удалось подключиться к базе данных")
        return None
        
    try:
        with connection.cursor() as cursor:
            # Проверка структуры таблицы Role
            cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'Role'
            """)
            columns = [col['COLUMN_NAME'].lower() for col in cursor.fetchall()]
            
            # Проверка наличия колонок
            has_display_name = 'display_name' in columns
            has_role_type = 'role_type' in columns
            has_is_system = 'is_system' in columns
            
            # Проверка, существует ли уже роль "Тестовая роль"
            if has_display_name:
                cursor.execute("SELECT * FROM Role WHERE display_name = %s", ("Тестовая роль",))
            else:
                cursor.execute("SELECT * FROM Role WHERE name = %s", ("test_role",))
                
            existing_role = cursor.fetchone()
            
            if existing_role:
                print(f"Роль 'Тестовая роль' уже существует с ID: {existing_role['id']}")
                role_id = existing_role['id']
            else:
                # Создание тестовой роли с учетом структуры таблицы
                if has_display_name and has_role_type and has_is_system:
                    cursor.execute(
                        "INSERT INTO Role (name, display_name, description, role_type, is_system) VALUES (%s, %s, %s, %s, %s)",
                        ("test_role", "Тестовая роль", "Роль для тестирования базовых модулей", "custom", 0)
                    )
                elif has_display_name:
                    cursor.execute(
                        "INSERT INTO Role (name, display_name, description) VALUES (%s, %s, %s)",
                        ("test_role", "Тестовая роль", "Роль для тестирования базовых модулей")
                    )
                else:
                    cursor.execute(
                        "INSERT INTO Role (name, description) VALUES (%s, %s)",
                        ("test_role", "Роль для тестирования базовых модулей")
                    )
                    
                connection.commit()
                role_id = cursor.lastrowid
                print(f"Создана роль 'Тестовая роль' с ID: {role_id}")
            
            # Проверяем наличие таблицы Module и RolePermission
            cursor.execute("SHOW TABLES LIKE 'Module'")
            has_module_table = cursor.fetchone() is not None
            
            cursor.execute("SHOW TABLES LIKE 'RolePermission'")
            has_permission_table = cursor.fetchone() is not None
            
            if has_module_table and has_permission_table:
                # Получение ID базовых модулей (dashboard, news)
                cursor.execute("SELECT id FROM Module WHERE name IN ('dashboard', 'news')")
                modules = cursor.fetchall()
                
                # Добавление разрешений на просмотр, создание и редактирование для этих модулей
                for module in modules:
                    module_id = module['id']
                    # Проверка существования разрешения
                    cursor.execute(
                        "SELECT * FROM RolePermission WHERE role_id = %s AND module_id = %s",
                        (role_id, module_id)
                    )
                    if not cursor.fetchone():
                        # Добавление разрешений (can_view=1, can_create=1, can_edit=1, can_delete=0)
                        cursor.execute(
                            "INSERT INTO RolePermission (role_id, module_id, can_view, can_create, can_edit, can_delete) VALUES (%s, %s, %s, %s, %s, %s)",
                            (role_id, module_id, 1, 1, 1, 0)
                        )
                        print(f"Добавлены разрешения для модуля с ID {module_id}")
                    else:
                        print(f"Разрешения для модуля с ID {module_id} уже существуют")
            else:
                print("Таблицы Module или RolePermission не найдены. Пропуск добавления разрешений.")
            
            connection.commit()
            return role_id
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Ошибка при создании тестовой роли: {e}")
        return None
    finally:
        if connection:
            connection.close()

def create_test_user(role_id):
    """Создание тестового пользователя с тестовой ролью"""
    if not role_id:
        print("Не удалось создать роль, невозможно создать пользователя")
        return None
        
    connection = create_db_connection()
    if not connection:
        print("Не удалось подключиться к базе данных")
        return None
        
    try:
        with connection.cursor() as cursor:
            # Проверка, существует ли уже пользователь "test_user"
            cursor.execute("SELECT * FROM User WHERE login = %s", ("test_user",))
            existing_user = cursor.fetchone()
            
            password = "test123"
            
            if existing_user:
                print(f"Пользователь 'test_user' уже существует с ID: {existing_user['id']}")
                user_id = existing_user['id']
            else:
                # Получим допустимые значения для статуса
                cursor.execute("SHOW COLUMNS FROM User LIKE 'status'")
                status_info = cursor.fetchone()
                valid_statuses = []
                
                if status_info and 'Type' in status_info and status_info['Type'].startswith('enum'):
                    # Извлекаем значения из enum('val1','val2',...)
                    enum_str = status_info['Type']
                    enum_values = enum_str[enum_str.find("(")+1:enum_str.find(")")].split(",")
                    valid_statuses = [val.strip("'").strip('"') for val in enum_values]
                
                status = "online" if "online" in valid_statuses else "Онлайн" if "Онлайн" in valid_statuses else ""
                
                # Создание пароля с использованием werkzeug
                hashed_password = generate_password_hash(password)
                
                # Проверяем структуру таблицы User
                cursor.execute("DESCRIBE User")
                columns = {col['Field']: col for col in cursor.fetchall()}
                
                # Подготавливаем SQL запрос в зависимости от имеющихся колонок
                fields = []
                values = []
                params = []
                
                # Базовые поля
                fields.append("login")
                values.append("%s")
                params.append("test_user")
                
                fields.append("password")
                values.append("%s")
                params.append(hashed_password)
                
                if "full_name" in columns:
                    fields.append("full_name")
                    values.append("%s")
                    params.append("Тестовый Пользователь")
                
                if "role" in columns:
                    fields.append("role")
                    values.append("%s")
                    params.append("user")
                
                if "department" in columns:
                    fields.append("department")
                    values.append("%s")
                    params.append("Тест")
                
                if "status" in columns:
                    fields.append("status")
                    values.append("%s")
                    params.append(status)
                
                # Формируем и выполняем SQL запрос
                sql = f"INSERT INTO User ({', '.join(fields)}) VALUES ({', '.join(values)})"
                cursor.execute(sql, params)
                connection.commit()
                
                user_id = cursor.lastrowid
                print(f"Создан пользователь 'test_user' с ID: {user_id}")
            
            # Проверка наличия таблицы UserRole для связи пользователя с ролью
            cursor.execute("SHOW TABLES LIKE 'UserRole'")
            has_user_role_table = cursor.fetchone() is not None
            
            if has_user_role_table:
                # Проверка существующей связи
                cursor.execute("SELECT * FROM UserRole WHERE user_id = %s AND role_id = %s", 
                              (user_id, role_id))
                if not cursor.fetchone():
                    # Создание связи пользователя с ролью
                    cursor.execute(
                        "INSERT INTO UserRole (user_id, role_id) VALUES (%s, %s)",
                        (user_id, role_id)
                    )
                    print(f"Пользователю с ID {user_id} назначена роль с ID {role_id}")
                else:
                    print(f"Пользователь с ID {user_id} уже имеет роль с ID {role_id}")
                
                connection.commit()
            else:
                # Если нет таблицы UserRole, проверяем есть ли поле role_id в таблице User
                cursor.execute("DESCRIBE User")
                columns = {col['Field']: col for col in cursor.fetchall()}
                
                if "role_id" in columns:
                    cursor.execute("UPDATE User SET role_id = %s WHERE id = %s", (role_id, user_id))
                    connection.commit()
                    print(f"Пользователю с ID {user_id} назначена роль с ID {role_id} через поле role_id")
                else:
                    print(f"Нет возможности назначить роль пользователю (отсутствуют таблица UserRole и поле role_id)")
            
            print(f"Логин: test_user")
            print(f"Пароль: {password}")
            return user_id
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Ошибка при создании тестового пользователя: {e}")
        return None
    finally:
        if connection:
            connection.close()

def main():
    print("=== Создание тестовой роли ===")
    role_id = create_test_role()
    
    if role_id:
        print("\n=== Создание тестового пользователя ===")
        user_id = create_test_user(role_id)
        
        if user_id:
            print("\n=== Инициализация завершена успешно ===")
            print("Вы можете войти в систему используя следующие учетные данные:")
            print("Логин: test_user")
            print("Пароль: test123")
            print("Пользователю назначена роль 'Тестовая роль'")
        else:
            print("\n=== Ошибка при создании пользователя ===")
    else:
        print("\n=== Ошибка при создании роли ===")

if __name__ == "__main__":
    main() 