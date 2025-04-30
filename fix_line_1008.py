#!/usr/bin/env python3

with open('/home/LetoBlack/app/callcenter/callcenter.py', 'r') as f:
    lines = f.readlines()

# Печатаем контекст вокруг строки 1008
print("Контекст до исправления:")
for i in range(max(0, 1008-5), min(len(lines), 1008+5)):
    print(f"{i+1}: {lines[i]}", end="")

# Ищем правильный уровень отступа из контекста
correct_indent = None
for i in range(max(0, 1000), 1008):
    line = lines[i]
    if "cursor.execute" in line and not line.strip().startswith("#"):
        correct_indent = len(line) - len(line.lstrip())
        print(f"\nНайден образец отступа в строке {i+1}: {line.rstrip()}")
        break

if correct_indent is not None:
    # Исправляем проблему в строке 1008
    content = lines[1007].strip()
    lines[1007] = " " * correct_indent + content + "\n"
    
    # Также исправляем отступы в блоке SQL-запроса (строки 1009-1013)
    for i in range(1008, 1013):
        if i < len(lines) and lines[i].strip():
            sql_indent = correct_indent + 4  # SQL запрос обычно имеет дополнительный отступ
            content = lines[i].strip()
            lines[i] = " " * sql_indent + content + "\n"

# Сохраняем исправленный файл
with open('/home/LetoBlack/app/callcenter/callcenter.py', 'w') as f:
    f.writelines(lines)

print("\nПосле исправления:")
with open('/home/LetoBlack/app/callcenter/callcenter.py', 'r') as f:
    fixed_lines = f.readlines()
    for i in range(max(0, 1008-5), min(len(fixed_lines), 1008+5)):
        print(f"{i+1}: {fixed_lines[i]}", end="") 