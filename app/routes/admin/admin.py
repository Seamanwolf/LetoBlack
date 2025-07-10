from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required as flask_login_required
from werkzeug.utils import secure_filename
from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash
from app.routes.admin import admin_routes_bp
from app.utils import admin_required, login_required, create_db_connection
import mysql.connector
import os
from os import path
import logging
import time
from PIL import Image

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@admin_routes_bp.route('/settings')
@flask_login_required
@admin_required
def settings():
    """Страница настроек системы"""
    # Получаем текущие настройки
    logger.debug(f"Static folder path: {current_app.static_folder}")
    logger.debug(f"Absolute path to static folder: {os.path.abspath(current_app.static_folder)}")
    
    # Проверяем наличие логотипа (сначала ищем PNG, затем BMP)
    logo_png_path = path.join(current_app.static_folder, 'images/logo.png')
    logo_bmp_path = path.join(current_app.static_folder, 'images/logo.bmp')
    
    logo_exists = path.exists(logo_png_path)
    logo_url = url_for('static', filename='images/logo.png')
    
    if not logo_exists and path.exists(logo_bmp_path):
        logo_exists = True
        logo_url = url_for('static', filename='images/logo.bmp')
    
    logger.debug(f"Logo PNG exists: {path.exists(logo_png_path)}")
    logger.debug(f"Logo BMP exists: {path.exists(logo_bmp_path)}")
    logger.debug(f"Logo URL: {logo_url if logo_exists else 'Не найден'}")
    
    # Проверяем наличие фонового изображения
    background_path = path.join(current_app.static_folder, 'images/real_estate_bg.jpg')
    background_exists = path.exists(background_path)
    background_url = url_for('static', filename='images/real_estate_bg.jpg')
    
    logger.debug(f"Background exists: {background_exists}")
    logger.debug(f"Background URL: {background_url if background_exists else 'Не найден'}")
    
    # Добавляем текущее время для предотвращения кеширования изображений
    now = int(time.time())
    
    return render_template('admin/settings.html',
                         logo_url=logo_url if logo_exists else None,
                         background_url=background_url if background_exists else None,
                         now=now)

@admin_routes_bp.route('/upload_logo', methods=['POST'])
@flask_login_required
@admin_required
def upload_logo():
    """Загрузка логотипа"""
    logger.debug("Начало загрузки логотипа")
    
    if 'logo' not in request.files:
        flash('Файл не выбран', 'danger')
        return redirect(url_for('admin.settings'))
    
    file = request.files['logo']
    logger.debug(f"Получен файл: {file.filename}, тип: {file.content_type}")
    
    if file.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(url_for('admin.settings'))
    
    if file and allowed_file(file.filename, {'png', 'jpg', 'jpeg', 'bmp'}):
        try:
            # Создаем нужную директорию
            upload_dir = os.path.join(current_app.static_folder, 'images')
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir, exist_ok=True)
                logger.debug(f"Создана директория: {upload_dir}")
            
            # Сначала сохраняем файл как есть, без обработки
            temp_filename = f"temp_{secure_filename(file.filename)}"
            temp_path = os.path.join(upload_dir, temp_filename)
            file.save(temp_path)
            logger.debug(f"Файл временно сохранен как: {temp_path}")
            
            # Теперь обрабатываем изображение
            try:
                # Сохраняем как PNG для поддержки прозрачности
                filename = 'logo.png'
                save_path = os.path.join(upload_dir, filename)
                
                # Проверяем, что файл существует
                if not os.path.exists(temp_path):
                    logger.error(f"Временный файл не был создан: {temp_path}")
                    flash('Ошибка при создании временного файла', 'danger')
                    return redirect(url_for('admin.settings'))
                
                # Загружаем изображение с помощью Pillow
                img = Image.open(temp_path)
                logger.debug(f"Изображение открыто с режимом: {img.mode}")
                
                # Если изображение уже имеет прозрачность (RGBA или PNG с прозрачностью)
                if img.mode == 'RGBA':
                    logger.debug("Изображение уже имеет прозрачность (RGBA)")
                    img.save(save_path, 'PNG')
                elif img.mode == 'P' and 'transparency' in img.info:
                    logger.debug("Изображение имеет палитру с прозрачностью")
                    img.save(save_path, 'PNG')
                else:
                    # Конвертируем в RGBA
                    logger.debug(f"Конвертируем изображение из {img.mode} в RGBA")
                    img = img.convert('RGBA')
                    
                    # Сохраняем без обработки прозрачности
                    img.save(save_path, 'PNG')
                    logger.debug(f"Изображение сохранено как PNG: {save_path}")
                
                # Удаляем временный файл
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.debug(f"Временный файл удален: {temp_path}")
                
                # Устанавливаем права доступа
                os.chmod(save_path, 0o777)
                logger.debug(f"Установлены права доступа 777 для: {save_path}")
                
                # Проверяем, что файл создан и доступен
                if os.path.exists(save_path):
                    file_size = os.path.getsize(save_path)
                    logger.debug(f"Файл создан успешно, размер: {file_size} байт")
                    
                    # Попытаемся копировать файл для дополнительного резервирования
                    backup_path = os.path.join(upload_dir, 'logo_backup.png')
                    import shutil
                    shutil.copy2(save_path, backup_path)
                    logger.debug(f"Создана резервная копия: {backup_path}")
                    
                    flash('Логотип успешно загружен', 'success')
                else:
                    logger.error(f"Файл не был создан после сохранения: {save_path}")
                    flash('Ошибка при сохранении файла', 'danger')
                
            except Exception as e:
                logger.exception(f"Ошибка при обработке изображения: {str(e)}")
                
                # Если не удалось обработать через Pillow, используем временный файл
                try:
                    if os.path.exists(temp_path):
                        # Просто копируем временный файл без обработки
                        import shutil
                        shutil.copy2(temp_path, os.path.join(upload_dir, 'logo.png'))
                        os.chmod(os.path.join(upload_dir, 'logo.png'), 0o777)
                        logger.debug("Использован временный файл в качестве логотипа")
                        
                        # Удаляем временный файл
                        os.remove(temp_path)
                        flash('Логотип загружен (без обработки прозрачности)', 'warning')
                    else:
                        flash('Не удалось обработать файл', 'danger')
                except Exception as e2:
                    logger.exception(f"Ошибка при использовании временного файла: {str(e2)}")
                    flash(f'Ошибка при обработке файла: {str(e2)}', 'danger')
            
        except Exception as e:
            logger.exception(f"Ошибка при загрузке логотипа: {str(e)}")
            flash(f'Ошибка при загрузке логотипа: {str(e)}', 'danger')
    else:
        flash('Недопустимый формат файла', 'danger')
    
    return redirect(url_for('admin.settings'))

@admin_routes_bp.route('/upload_background', methods=['POST'])
@flask_login_required
@admin_required
def upload_background():
    """Загрузка фонового изображения"""
    logger.debug("Начало загрузки фонового изображения")
    
    if 'background' not in request.files:
        flash('Файл не выбран', 'danger')
        return redirect(url_for('admin.settings'))
    
    file = request.files['background']
    
    if file.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(url_for('admin.settings'))
    
    if file and allowed_file(file.filename, {'png', 'jpg', 'jpeg'}):
        try:
            # Создаем нужную директорию
            upload_dir = os.path.join(current_app.static_folder, 'images')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Сохраняем файл
            filename = 'real_estate_bg.jpg'
            save_path = os.path.join(upload_dir, filename)
            
            file.save(save_path)
            logger.info(f"Фоновое изображение успешно сохранено в {save_path}")
            
            # Даем полные права для уверенности
            os.chmod(save_path, 0o777)
            
            flash('Фоновое изображение успешно загружено', 'success')
            
        except Exception as e:
            logger.exception(f"Ошибка при загрузке фонового изображения: {str(e)}")
            flash(f'Ошибка при загрузке фонового изображения: {str(e)}', 'danger')
    else:
        flash('Недопустимый формат файла', 'danger')
    
    return redirect(url_for('admin.settings'))

@admin_routes_bp.route('/delete_logo', methods=['POST'])
@flask_login_required
@admin_required
def delete_logo():
    """Удаление логотипа"""
    logger.debug("Начало удаления логотипа")
    
    try:
        logo_path = os.path.join(current_app.static_folder, 'images', 'logo.png')
        
        if os.path.exists(logo_path):
            os.remove(logo_path)
            logger.info(f"Логотип успешно удален: {logo_path}")
            flash('Логотип успешно удален', 'success')
        else:
            logger.warning(f"Логотип не найден: {logo_path}")
            flash('Логотип не найден', 'warning')
    except Exception as e:
        logger.exception(f"Ошибка при удалении логотипа: {str(e)}")
        flash(f'Ошибка при удалении логотипа: {str(e)}', 'danger')
    
    return redirect(url_for('admin.settings'))

@admin_routes_bp.route('/delete_background', methods=['POST'])
@flask_login_required
@admin_required
def delete_background():
    """Удаление фонового изображения"""
    logger.debug("Начало удаления фонового изображения")
    
    try:
        bg_path = os.path.join(current_app.static_folder, 'images', 'real_estate_bg.jpg')
        
        if os.path.exists(bg_path):
            os.remove(bg_path)
            logger.info(f"Фоновое изображение успешно удалено: {bg_path}")
            flash('Фоновое изображение успешно удалено', 'success')
        else:
            logger.warning(f"Фоновое изображение не найдено: {bg_path}")
            flash('Фоновое изображение не найдено', 'warning')
    except Exception as e:
        logger.exception(f"Ошибка при удалении фонового изображения: {str(e)}")
        flash(f'Ошибка при удалении фонового изображения: {str(e)}', 'danger')
    
    return redirect(url_for('admin.settings'))

def allowed_file(filename, allowed_extensions):
    """Проверка расширения файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions 