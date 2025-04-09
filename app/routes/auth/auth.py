from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user, login_user
from werkzeug.security import check_password_hash
import mysql.connector
from os import path
from flask import current_app

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа в систему"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Введите имя пользователя и пароль', 'danger')
            return redirect(url_for('auth.login'))
        
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        try:
            cursor.execute("SELECT * FROM User WHERE login = %s", (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password'], password):
                user_obj = User(user['id'], user['login'], user['email'], user['role'])
                login_user(user_obj)
                
                # Обновляем статус пользователя на "Онлайн"
                cursor.execute("UPDATE User SET status = 'Онлайн' WHERE id = %s", (user['id'],))
                connection.commit()
                
                next_page = request.args.get('next')
                return redirect(next_page or url_for('main.index'))
            else:
                flash('Неверное имя пользователя или пароль', 'danger')
        except mysql.connector.Error as err:
            flash(f'Ошибка: {err}', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    # Проверяем наличие логотипа
    logo_png_path = path.join(current_app.static_folder, 'images/logo.png')
    logo_bmp_path = path.join(current_app.static_folder, 'images/logo.bmp')
    
    logo_exists = path.exists(logo_png_path)
    logo_url = url_for('static', filename='images/logo.png')
    
    if not logo_exists and path.exists(logo_bmp_path):
        logo_exists = True
        logo_url = url_for('static', filename='images/logo.bmp')
    
    return render_template('auth/login.html', logo_url=logo_url if logo_exists else None) 