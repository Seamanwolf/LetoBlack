#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pymysql
import hashlib
import secrets
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

def create_db_connection():
    """Создание подключения к базе данных"""
    connection = pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'mydb'),
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection

def hash_password(password):
    """Хеширование пароля с солью"""
    salt = secrets.token_hex(8)
    hash_obj = hashlib.sha256((password + salt).encode())
    password_hash = hash_obj.hexdigest()
    return f"{password_hash}:{salt}"

def create_test_role():
    """Создание тестовой роли с доступом к ВАТС и Новости"""
    connection = create_db_connection()
    try:
        with connection.cursor() as cursor:
            # Проверка, существует ли уже роль "Тестовая роль"
            cursor.execute("SELECT * FROM Role WHERE role_name = %s", ("Тестовая роль",))
            existing_role = cursor.fetchone()
            
            if existing_role:
                print(f"Роль 'Тестовая роль' уже существует с ID: {existing_role['id']}")
                role_id = existing_role['id']
            else:
                # Создание тестовой роли
                cursor.execute(
                    "INSERT INTO Role (role_name, description) VALUES (%s, %s)",
                    ("Тестовая роль", "Роль для тестирования модулей ВАТС и Новости")
                )
                connection.commit()
                role_id = cursor.lastrowid
                print(f"Создана роль 'Тестовая роль' с ID: {role_id}")
            
            # Получение ID модулей ВАТС и Новости
            cursor.execute("SELECT id FROM Module WHERE module_name IN ('ВАТС', 'Новости')")
            modules = cursor.fetchall()
            
            # Добавление разрешений на просмотр, редактирование и удаление для этих модулей
            for module in modules:
                module_id = module['id']
                # Проверка существования разрешения
                cursor.execute(
                    "SELECT * FROM Permission WHERE role_id = %s AND module_id = %s",
                    (role_id, module_id)
                )
                if not cursor.fetchone():
                    # Добавление разрешений (can_view=1, can_edit=1, can_delete=1)
                    cursor.execute(
                        "INSERT INTO Permission (role_id, module_id, can_view, can_edit, can_delete) VALUES (%s, %s, %s, %s, %s)",
                        (role_id, module_id, 1, 1, 1)
                    )
                    print(f"Добавлены разрешения для модуля с ID {module_id}")
                else:
                    print(f"Разрешения для модуля с ID {module_id} уже существуют")
            
            connection.commit()
            return role_id
    finally:
        connection.close()

def create_test_user(role_id):
    """Создание тестового пользователя с тестовой ролью"""
    connection = create_db_connection()
    try:
        with connection.cursor() as cursor:
            # Проверка, существует ли уже пользователь "test_user"
            cursor.execute("SELECT * FROM User WHERE username = %s", ("test_user",))
            existing_user = cursor.fetchone()
            
            if existing_user:
                print(f"Пользователь 'test_user' уже существует с ID: {existing_user['id']}")
                return existing_user['id']
            
            # Хеширование пароля
            password = "test123"
            hashed_password = hash_password(password)
            
            # Создание тестового пользователя
            cursor.execute(
                """INSERT INTO User 
                   (username, password, email, first_name, last_name, role_id, status, is_admin) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                ("test_user", hashed_password, "test@example.com", "Тестовый", "Пользователь", 
                 role_id, "Онлайн", 0)
            )
            connection.commit()
            user_id = cursor.lastrowid
            print(f"Создан пользователь 'test_user' с ID: {user_id}")
            print(f"Логин: test_user")
            print(f"Пароль: {password}")
            return user_id
    finally:
        connection.close()

def main():
    try:
        # Создание тестовой роли
        print("=== Создание тестовой роли ===")
        role_id = create_test_role()
        
        # Создание тестового пользователя
        print("\n=== Создание тестового пользователя ===")
        user_id = create_test_user(role_id)
        
        print("\n=== Инициализация завершена успешно ===")
        print("Вы можете войти в систему используя следующие учетные данные:")
        print("Логин: test_user")
        print("Пароль: test123")
        print("Пользователю назначена роль 'Тестовая роль' с доступом к модулям ВАТС и Новости")
    except Exception as e:
        print(f"Ошибка при инициализации: {str(e)}")

if __name__ == "__main__":
    main() 