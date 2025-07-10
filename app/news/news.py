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

@news_bp.route('/news')
@login_required
def index():
    """Отображает страницу с новостями с учетом ролей"""
    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    current_user_role_id = getattr(current_user, 'role_id', None)
    if current_user_role_id is None:
        # Если по какой-то причине role_id не загружен, не показываем новости
        news = []
    else:
        # Этот запрос выбирает новости, если:
        # 1. Новость опубликована и ее время публикации уже наступило.
        # 2. Роль текущего пользователя есть в списке ролей для этой новости (или новость для всех).
        # "Для всех" ролей - это когда в NewsRoles есть записи для всех существующих ролей.
        query = """
        SELECT n.*, u.full_name as created_by_name
        FROM News n
        LEFT JOIN User u ON n.created_by = u.id
        WHERE n.is_published = 1
          AND (n.publish_at IS NULL OR n.publish_at <= NOW())
          AND EXISTS (
            SELECT 1
            FROM NewsRoles nr
            WHERE nr.news_id = n.id AND nr.role_id = %s
        )
        ORDER BY n.publish_at DESC, n.created_at DESC;
        """
        cursor.execute(query, (current_user_role_id,))
        news = cursor.fetchall()
    
    # Получаем роли для формы создания новостей (только для админов)
    roles = []
    if current_user.has_role('admin'):
        cursor.execute("SELECT id, name FROM Role")
        roles = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('news/index.html', news=news, roles=roles)

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
    SELECT n.*, u.full_name as created_by_name
    FROM News n 
    LEFT JOIN User u ON n.created_by = u.id
    WHERE 1=1
    """
    params = []
    
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
    SELECT n.*, u.full_name as created_by_name
    FROM News n 
    LEFT JOIN User u ON n.created_by = u.id
    WHERE n.id = %s
    """
    cursor.execute(query, (news_id,))
    news = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not news:
        flash('Новость не найдена или у вас нет прав для ее просмотра', 'danger')
        return redirect(url_for('news.index'))
    
    return render_template('news/view.html', news=news)

@news_bp.route('/news/react/<int:news_id>', methods=['POST'])
@news_bp.route('/react/<int:news_id>', methods=['POST'])
@login_required
def react_to_news(news_id):
    """Добавить или обновить реакцию на новость"""
    reaction_type = request.json.get('reaction_type')
    
    if reaction_type not in ['positive', 'neutral', 'negative']:
        return jsonify({'success': False, 'message': 'Неверный тип реакции'}), 400
    
    conn = create_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, есть ли уже реакция от этого пользователя на эту новость
        cursor.execute("""
            SELECT id FROM NewsReactions 
            WHERE news_id = %s AND user_id = %s
        """, (news_id, current_user.id))
        
        existing_reaction = cursor.fetchone()
        
        if existing_reaction:
            # Обновляем существующую реакцию
            cursor.execute("""
                UPDATE NewsReactions 
                SET reaction_type = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (reaction_type, existing_reaction[0]))
        else:
            # Создаем новую реакцию
            cursor.execute("""
                INSERT INTO NewsReactions (news_id, user_id, reaction_type) 
                VALUES (%s, %s, %s)
            """, (news_id, current_user.id, reaction_type))
        
        conn.commit()
        
        # Получаем обновленную статистику реакций
        cursor.execute("""
            SELECT reaction_type, COUNT(*) as count 
            FROM NewsReactions 
            WHERE news_id = %s 
            GROUP BY reaction_type
        """, (news_id,))
        
        stats = {row[0]: row[1] for row in cursor.fetchall()}
        
        return jsonify({
            'success': True,
            'stats': stats,
            'user_reaction': reaction_type
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@news_bp.route('/news/reactions/<int:news_id>')
@news_bp.route('/reactions/<int:news_id>')
@login_required
def get_news_reactions(news_id):
    """Получить статистику реакций на новость"""
    conn = create_db_connection()
    cursor = conn.cursor()
    
    try:
        # Получаем статистику реакций
        cursor.execute("""
            SELECT reaction_type, COUNT(*) as count 
            FROM NewsReactions 
            WHERE news_id = %s 
            GROUP BY reaction_type
        """, (news_id,))
        
        stats = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Получаем реакцию текущего пользователя
        cursor.execute("""
            SELECT reaction_type 
            FROM NewsReactions 
            WHERE news_id = %s AND user_id = %s
        """, (news_id, current_user.id))
        
        user_reaction = cursor.fetchone()
        user_reaction = user_reaction[0] if user_reaction else None
        
        return jsonify({
            'stats': stats,
            'user_reaction': user_reaction
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close() 
        