#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re

def update_css_links(directory):
    """
    Обновляет ссылки на CSS файлы в HTML шаблонах.
    Заменяет styles.css на css/common.css
    """
    html_files = []
    
    # Рекурсивно собираем все HTML файлы
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                html_files.append(os.path.join(root, file))
    
    # Шаблон для поиска ссылок на styles.css
    old_css_pattern = r'<link\s+rel=["\']stylesheet["\']\s+href=["\']{{ url_for\([\'\"]static[\'\"]\,\s*filename=[\'\"](styles\.css)[\'\"]\) }}'
    
    # Новая строка с css/common.css и случайным параметром для сброса кеша
    new_css_link = r'<link rel="stylesheet" href="{{ url_for(\'static\', filename=\'css/common.css\') }}?v={{ range(1, 100000) | random }}'
    
    updated_count = 0
    
    for html_file in html_files:
        with open(html_file, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Проверяем, есть ли ссылка на styles.css
        if re.search(old_css_pattern, content):
            # Заменяем ссылку
            updated_content = re.sub(old_css_pattern, new_css_link, content)
            
            # Записываем обновленное содержимое
            with open(html_file, 'w', encoding='utf-8') as file:
                file.write(updated_content)
            
            updated_count += 1
            print(f"Обновлен файл: {html_file}")
    
    print(f"\nВсего обновлено файлов: {updated_count}")

if __name__ == "__main__":
    # Директория с шаблонами
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'templates')
    update_css_links(templates_dir) 