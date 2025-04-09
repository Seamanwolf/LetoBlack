from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import datetime
import uuid
from . import news_bp
from app.utils import create_db_connection, admin_required
import time

# Поддерживаемые форматы изображений
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Проверка допустимости формата файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@news_bp.route('/')
@login_required
def index():
    """Отображает страницу с новостями"""
    # Получаем список всех новостей
    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Получаем новости, доступные текущему пользователю
    query = """
    SELECT n.*, u.full_name as author_name 
    FROM News n 
    LEFT JOIN User u ON n.author_id = u.id
    LEFT JOIN NewsRoles nr ON n.id = nr.news_id
    WHERE nr.role_id = %s OR nr.role_id = 0
    GROUP BY n.id
    ORDER BY n.created_at DESC
    """
    cursor.execute(query, (current_user.role_id,))
    news = cursor.fetchall()
    
    # Получаем роли для формы создания новостей
    cursor.execute("SELECT id, name FROM Role WHERE id > 0")
    roles = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('news/index.html', news=news, roles=roles)

@news_bp.route('/create', methods=['POST'])
@login_required
@admin_required
def create_news():
    """Создать новую новость"""
    # Получаем данные из формы
    title = request.form.get('newsTitle')
    content = request.form.get('newsContent')
    category = request.form.get('newsCategory')
    selected_roles = request.form.getlist('newsRoles')
    
    # Для всех ролей используем id = 0
    if 'all_roles' in request.form:
        selected_roles = ['0']  # 0 означает "все роли"
    
    # Проверяем обязательные поля
    if not title or not content:
        flash('Заполните все обязательные поля', 'danger')
        return redirect(url_for('news.index'))
    
    # Получаем файл изображения, если есть
    image_filename = None
    if 'newsImage' in request.files:
        image_file = request.files['newsImage']
        if image_file and image_file.filename and allowed_file(image_file.filename):
            # Генерируем уникальное имя файла
            original_filename = secure_filename(image_file.filename)
            extension = original_filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{int(time.time())}_{uuid.uuid4().hex}.{extension}"
            
            # Создаем папку для изображений новостей, если не существует
            news_images_folder = os.path.join('app', 'static', 'images', 'news')
            os.makedirs(news_images_folder, exist_ok=True)
            
            # Сохраняем файл
            image_path = os.path.join(news_images_folder, unique_filename)
            image_file.save(image_path)
            image_filename = unique_filename
    
    # Сохраняем новость в базу данных
    conn = create_db_connection()
    cursor = conn.cursor()
    
    try:
        # Вставляем новость
        query = """
        INSERT INTO News (title, content, category, image, author_id, created_at) 
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        now = datetime.datetime.now()
        cursor.execute(query, (title, content, category, image_filename, current_user.id, now))
        news_id = cursor.lastrowid
        
        # Вставляем связи с ролями
        if selected_roles:
            for role_id in selected_roles:
                cursor.execute(
                    "INSERT INTO NewsRoles (news_id, role_id) VALUES (%s, %s)",
                    (news_id, role_id)
                )
        
        conn.commit()
        flash('Новость успешно опубликована', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при сохранении новости: {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('news.index'))

@news_bp.route('/edit/<int:news_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_news(news_id):
    """Редактировать новость"""
    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Получаем данные из формы
        title = request.form.get('newsTitle')
        content = request.form.get('newsContent')
        category = request.form.get('newsCategory')
        selected_roles = request.form.getlist('newsRoles')
        
        # Для всех ролей используем id = 0
        if 'all_roles' in request.form:
            selected_roles = ['0']  # 0 означает "все роли"
        
        # Проверяем обязательные поля
        if not title or not content:
            flash('Заполните все обязательные поля', 'danger')
            return redirect(url_for('news.edit_news', news_id=news_id))
        
        # Получаем текущую информацию о новости
        cursor.execute("SELECT image FROM News WHERE id = %s", (news_id,))
        current_news = cursor.fetchone()
        current_image = current_news['image'] if current_news else None
        
        # Обработка изображения, если оно изменилось
        image_filename = current_image
        if 'newsImage' in request.files:
            image_file = request.files['newsImage']
            if image_file and image_file.filename and allowed_file(image_file.filename):
                # Генерируем уникальное имя файла
                original_filename = secure_filename(image_file.filename)
                extension = original_filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{int(time.time())}_{uuid.uuid4().hex}.{extension}"
                
                # Создаем папку для изображений новостей, если не существует
                news_images_folder = os.path.join('app', 'static', 'images', 'news')
                os.makedirs(news_images_folder, exist_ok=True)
                
                # Сохраняем файл
                image_path = os.path.join(news_images_folder, unique_filename)
                image_file.save(image_path)
                image_filename = unique_filename
                
                # Удаляем старое изображение, если оно есть
                if current_image:
                    old_image_path = os.path.join(news_images_folder, current_image)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
        
        try:
            # Обновляем новость
            query = """
            UPDATE News SET title = %s, content = %s, category = %s, image = %s, updated_at = %s
            WHERE id = %s
            """
            now = datetime.datetime.now()
            cursor.execute(query, (title, content, category, image_filename, now, news_id))
            
            # Удаляем старые связи с ролями и добавляем новые
            cursor.execute("DELETE FROM NewsRoles WHERE news_id = %s", (news_id,))
            
            if selected_roles:
                for role_id in selected_roles:
                    cursor.execute(
                        "INSERT INTO NewsRoles (news_id, role_id) VALUES (%s, %s)",
                        (news_id, role_id)
                    )
            
            conn.commit()
            flash('Новость успешно обновлена', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Ошибка при обновлении новости: {str(e)}', 'danger')
        finally:
            cursor.close()
            conn.close()
        
        return redirect(url_for('news.index'))
    
    # Получаем информацию о новости для редактирования
    cursor.execute("SELECT * FROM News WHERE id = %s", (news_id,))
    news = cursor.fetchone()
    
    if not news:
        cursor.close()
        conn.close()
        flash('Новость не найдена', 'danger')
        return redirect(url_for('news.index'))
    
    # Получаем связанные роли
    cursor.execute("SELECT role_id FROM NewsRoles WHERE news_id = %s", (news_id,))
    news_roles = [row['role_id'] for row in cursor.fetchall()]
    
    # Получаем все роли для формы
    cursor.execute("SELECT id, name FROM Role WHERE id > 0")
    roles = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('news/edit.html', news=news, roles=roles, news_roles=news_roles)

@news_bp.route('/delete/<int:news_id>', methods=['POST'])
@login_required
@admin_required
def delete_news(news_id):
    """Удалить новость"""
    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Получаем информацию о новости для удаления изображения
    cursor.execute("SELECT image FROM News WHERE id = %s", (news_id,))
    news = cursor.fetchone()
    
    try:
        # Удаляем связи с ролями
        cursor.execute("DELETE FROM NewsRoles WHERE news_id = %s", (news_id,))
        
        # Удаляем новость
        cursor.execute("DELETE FROM News WHERE id = %s", (news_id,))
        
        # Удаляем изображение, если оно есть
        if news and news['image']:
            image_path = os.path.join('app', 'static', 'images', 'news', news['image'])
            if os.path.exists(image_path):
                os.remove(image_path)
        
        conn.commit()
        flash('Новость успешно удалена', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при удалении новости: {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('news.index'))

@news_bp.route('/api/news', methods=['GET'])
@login_required
def api_get_news():
    """API для получения новостей"""
    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Получаем параметры фильтрации
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')
    
    # Базовый запрос
    query = """
    SELECT n.*, u.full_name as author_name 
    FROM News n 
    LEFT JOIN User u ON n.author_id = u.id
    LEFT JOIN NewsRoles nr ON n.id = nr.news_id
    WHERE (nr.role_id = %s OR nr.role_id = 0)
    """
    params = [current_user.role_id]
    
    # Добавляем фильтры
    if category != 'all':
        query += " AND n.category = %s"
        params.append(category)
    
    if search:
        query += " AND (n.title LIKE %s OR n.content LIKE %s)"
        search_param = f"%{search}%"
        params.append(search_param)
        params.append(search_param)
    
    query += " GROUP BY n.id ORDER BY n.created_at DESC"
    
    cursor.execute(query, tuple(params))
    news = cursor.fetchall()
    
    # Преобразуем datetime объекты в строки
    for item in news:
        if 'created_at' in item and item['created_at']:
            item['created_at'] = item['created_at'].strftime('%d.%m.%Y %H:%M')
        if 'updated_at' in item and item['updated_at']:
            item['updated_at'] = item['updated_at'].strftime('%d.%m.%Y %H:%M')
    
    cursor.close()
    conn.close()
    
    return jsonify(news)

@news_bp.route('/view/<int:news_id>')
@login_required
def view_news(news_id):
    """Просмотр отдельной новости"""
    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Получаем информацию о новости
    query = """
    SELECT n.*, u.full_name as author_name 
    FROM News n 
    LEFT JOIN User u ON n.author_id = u.id
    LEFT JOIN NewsRoles nr ON n.id = nr.news_id
    WHERE n.id = %s AND (nr.role_id = %s OR nr.role_id = 0)
    """
    cursor.execute(query, (news_id, current_user.role_id))
    news = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not news:
        flash('Новость не найдена или у вас нет прав для ее просмотра', 'danger')
        return redirect(url_for('news.index'))
    
    return render_template('news/view.html', news=news) 