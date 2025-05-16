#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil

def backup_file(file_path):
    """Создает резервную копию файла перед удалением"""
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'css_backup')
    
    # Создаем директорию для резервных копий, если она не существует
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # Имя файла без пути
    file_name = os.path.basename(file_path)
    
    # Копируем файл в директорию резервных копий
    backup_path = os.path.join(backup_dir, file_name)
    shutil.copy2(file_path, backup_path)
    
    print(f"Создана резервная копия: {backup_path}")
    
    return backup_path

def remove_old_css_files():
    """Удаляет устаревшие CSS файлы после миграции на common.css"""
    # Список устаревших CSS файлов
    files_to_remove = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'styles.css'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'templates', 'styles.css')
    ]
    
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            # Создаем резервную копию перед удалением
            backup_file(file_path)
            
            # Удаляем файл
            os.remove(file_path)
            print(f"Удален файл: {file_path}")
        else:
            print(f"Файл не найден: {file_path}")
    
    print("\nОчистка завершена.")

if __name__ == "__main__":
    remove_old_css_files() 