from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
import bleach
from app.decorators import admin_required
from app.db_connection import get_connection
from app.models.news import News
from datetime import datetime

bp = Blueprint('admin_news', __name__, url_prefix='/admin')

@bp.route('/news')
@login_required
@admin_required
def list_news():
    news_list = News.get_all(include_unpublished=True)
    return render_template('admin/news/list.html', news=news_list)

@bp.route('/news/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_news():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM Role")
    roles = cursor.fetchall()
    cursor.close()
    conn.close()

    if request.method == 'POST':
        try:
            title = request.form.get('title')
            content = request.form.get('content')
            
            allowed_tags = ['h1', 'h2', 'h3', 'p', 'br', 'strong', 'em', 'u', 'ol', 'li', 'ul', 'a']
            allowed_attrs = {'a': ['href', 'title']}
            cleaned_content = bleach.clean(content, tags=allowed_tags, attributes=allowed_attrs)

            publish_at_str = request.form.get('publish_at')
            is_published_now = request.form.get('publish_now') == 'on'
            
            publish_at = None
            if is_published_now:
                publish_at = datetime.utcnow()
            elif publish_at_str:
                publish_at = datetime.fromisoformat(publish_at_str)

            if not title or not cleaned_content:
                flash('Заголовок и содержание обязательны.', 'warning')
                return render_template('admin/news/create.html', roles=roles, title=title, content=content)

            news = News(
                title=title,
                body=cleaned_content,
                created_by=current_user.id,
                publish_at=publish_at,
                is_published=is_published_now
            )

            if request.form.get('all_roles'):
                selected_roles = [str(role['id']) for role in roles]
            else:
                selected_roles = request.form.getlist('roles')
            
            news.save_with_roles(request.files.get('image'), selected_roles)

            flash('Новость успешно создана', 'success')
            return redirect(url_for('admin_news.list_news'))
        except Exception as e:
            flash(f'Произошла ошибка при создании новости: {e}', 'danger')

    return render_template('admin/news/create.html', roles=roles)

@bp.route('/news/edit/<int:news_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_news(news_id):
    news = News.get_by_id(news_id)
    if not news:
        flash('Новость не найдена', 'danger')
        return redirect(url_for('admin_news.list_news'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM Role")
    all_roles = cursor.fetchall()
    cursor.close()
    conn.close()

    if request.method == 'POST':
        try:
            news.title = request.form.get('title')
            
            content = request.form.get('content')
            allowed_tags = ['h1', 'h2', 'h3', 'p', 'br', 'strong', 'em', 'u', 'ol', 'li', 'ul', 'a']
            allowed_attrs = {'a': ['href', 'title']}
            news.body = bleach.clean(content, tags=allowed_tags, attributes=allowed_attrs)

            publish_at_str = request.form.get('publish_at')
            is_published_now = request.form.get('publish_now') == 'on'

            if is_published_now:
                news.publish_at = datetime.utcnow()
                news.is_published = True
            elif publish_at_str:
                news.publish_at = datetime.fromisoformat(publish_at_str)
            else:
                news.publish_at = None
                news.is_published = False

            if request.form.get('all_roles'):
                selected_roles = [str(r['id']) for r in all_roles]
            else:
                selected_roles = request.form.getlist('roles')
            
            news.save_with_roles(request.files.get('image'), selected_roles)

            flash('Новость успешно обновлена', 'success')
            return redirect(url_for('admin_news.list_news'))
        except Exception as e:
            flash(f'Произошла ошибка при обновлении новости: {e}', 'danger')
    
    news_roles = News.get_roles(news.id)
    return render_template('admin/news/edit.html', news=news, roles=all_roles, news_roles=news_roles)

@bp.route('/news/delete/<int:news_id>', methods=['POST'])
@login_required
@admin_required
def delete_news(news_id):
    try:
        News.delete(news_id)
        flash('Новость удалена.', 'success')
    except Exception as e:
        flash(f'Ошибка при удалении новости: {e}', 'danger')
    return redirect(url_for('admin_news.list_news'))