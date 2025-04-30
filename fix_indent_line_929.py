#!/usr/bin/env python3

with open('/home/LetoBlack/app/callcenter/callcenter.py', 'r') as f:
    lines = f.readlines()

# Печатаем контекст вокруг строки 929
print("Контекст до исправления:")
for i in range(max(0, 929-5), min(len(lines), 929+5)):
    print(f"{i+1}: {lines[i]}", end="")

# Исправляем проблему в строке 929
if len(lines) >= 929:
    # Уровень отступа в строке 929 должен соответствовать отступу предыдущих строк в блоке
    # Удаляем лишние пробелы
    lines[928] = lines[928].rstrip() + "\n"  # Строка перед проблемной строкой
    
    # Определяем правильный отступ из контекста
    lines[928-1] = lines[928-1].rstrip() + "\n"
    indent_level = len(lines[928-1]) - len(lines[928-1].lstrip())
    
    # Применяем правильный отступ
    content = lines[928].strip()
    lines[928] = " " * indent_level + content + "\n"

# Сохраняем исправленный файл
with open('/home/LetoBlack/app/callcenter/callcenter.py', 'w') as f:
    f.writelines(lines)

print("\nПосле исправления:")
with open('/home/LetoBlack/app/callcenter/callcenter.py', 'r') as f:
    fixed_lines = f.readlines()
    for i in range(max(0, 929-5), min(len(fixed_lines), 929+5)):
        print(f"{i+1}: {fixed_lines[i]}", end="") 