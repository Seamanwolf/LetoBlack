@admin_bp.route('/api/add_broker', methods=['POST'])
@login_required
def add_broker():
    """Добавление нового сотрудника"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Недостаточно прав'}), 403

    try:
        # Получаем данные из формы
        login = request.form.get('login')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        department_id = request.form.get('department_id')
        position = request.form.get('position', '')
        hire_date = request.form.get('hire_date')
        personal_email = request.form.get('personal_email', '')
        pc_login = request.form.get('pc_login', '')
        pc_password = request.form.get('pc_password', '')
        birth_date = request.form.get('birth_date')
        ukc_kc = request.form.get('ukc_kc', 'УКЦ')

        # Проверяем обязательные поля
        if not all([login, password, full_name]):
            return jsonify({'success': False, 'message': 'Не заполнены обязательные поля'}), 400

        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Проверяем, существует ли пользователь с таким логином
            cursor.execute("SELECT id FROM User WHERE login = %s", (login,))
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Пользователь с таким логином уже существует'}), 409

            # Получаем название отдела по ID
            department = ''
            if department_id:
                try:
                    department_id = int(department_id)
                    cursor.execute("SELECT name FROM Department WHERE id = %s", (department_id,))
                    dept_result = cursor.fetchone()
                    if not dept_result:
                        return jsonify({'success': False, 'message': 'Указанный отдел не найден'}), 404
                    department = dept_result['name']
                except ValueError:
                    return jsonify({'success': False, 'message': 'Неверный формат ID отдела'}), 400

            # Хешируем пароль
            hashed_password = generate_password_hash(password)

            # Форматируем даты
            try:
                if hire_date:
                    hire_date = datetime.strptime(hire_date, '%Y-%m-%d').date()
                if birth_date:
                    birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
            except ValueError as e:
                return jsonify({'success': False, 'message': f'Неверный формат даты: {str(e)}'}), 400

            # Добавляем пользователя
            insert_query = """
            INSERT INTO User 
            (login, password, full_name, Phone, department, role, hire_date, personal_email, 
            pc_login, pc_password, birth_date, ukc_kc, position, department_id) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(
                insert_query, 
                (login, hashed_password, full_name, phone, department, 'user', hire_date, 
                 personal_email, pc_login, pc_password, birth_date, ukc_kc, position, department_id)
            )
            
            user_id = cursor.lastrowid

            # Регистрация события в истории
            cursor.execute(
                "INSERT INTO UserHistory (user_id, changed_field, old_value, new_value, changed_by, changed_at) VALUES (%s, %s, %s, %s, %s, NOW())",
                (user_id, 'create_account', '', 'Аккаунт создан', current_user.id)
            )
            
            conn.commit()
            current_app.logger.info(f"Добавлен новый пользователь: {login}, id: {user_id}")
            
            return jsonify({'success': True, 'message': 'Пользователь успешно добавлен'})

        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Ошибка при добавлении пользователя: {str(e)}")
            return jsonify({'success': False, 'message': f'Ошибка при добавлении пользователя: {str(e)}'}), 500

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        current_app.logger.error(f"Критическая ошибка в методе add_broker: {str(e)}")
        return jsonify({'success': False, 'message': f'Критическая ошибка: {str(e)}'}), 500 