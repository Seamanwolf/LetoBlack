#!/usr/bin/env python3
import re

def fix_indentation(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Исправляем известную проблему индентации на строке 1012
    if len(lines) >= 1012:
        print("Проверяем строку 1012")
        for i in range(max(0, 1012-5), min(len(lines), 1012+5)):
            print(f"{i+1}: {lines[i]}", end="")
        
        # Если строка 1012 имеет лишний отступ
        if lines[1011].strip().startswith("# Получаем список брокеров") and re.match(r'^\s{8,}cursor\.execute', lines[1011]):
            # Определяем правильный отступ
            prev_lines = [lines[i] for i in range(1010, 1011) if not lines[i].strip().startswith("#") and lines[i].strip()]
            if prev_lines:
                correct_indent = len(prev_lines[0]) - len(prev_lines[0].lstrip())
                content = lines[1011].strip()
                lines[1011] = " " * correct_indent + content + "\n"
                print(f"\nИсправлена строка 1012 на: {lines[1011]}")
    
    # Исправляем проблему в функции report_dashboard (около строки 1419)
    # Ищем начало функции
    func_start = -1
    for i, line in enumerate(lines):
        if "def report_dashboard()" in line:
            func_start = i
            break
    
    if func_start != -1:
        # Ищем блок try в функции
        try_line = -1
        for i in range(func_start, min(func_start + 20, len(lines))):
            if re.match(r'^\s+try\s*:\s*$', lines[i]):
                try_line = i
                break
        
        if try_line != -1:
            print(f"\nНайден блок try в report_dashboard на строке {try_line+1}")
            # Проверяем отступы после try
            expected_indent = len(lines[try_line]) - len(lines[try_line].lstrip()) + 4  # try + 4 пробела
            
            # Проверяем следующие 10 строк после try
            for i in range(try_line + 1, min(try_line + 11, len(lines))):
                if lines[i].strip() and not lines[i].strip().startswith('#'):
                    current_indent = len(lines[i]) - len(lines[i].lstrip())
                    if current_indent != expected_indent:
                        print(f"Неверный отступ в строке {i+1}: {lines[i].rstrip()}")
                        content = lines[i].strip()
                        lines[i] = " " * expected_indent + content + "\n"
                        print(f"Исправлено на: {lines[i].rstrip()}")
    
    # Сохраняем исправленный файл
    with open(file_path, 'w') as f:
        f.writelines(lines)
    
    print("\nВсе исправления внесены в файл.")

fix_indentation('/home/LetoBlack/app/callcenter/callcenter.py') 