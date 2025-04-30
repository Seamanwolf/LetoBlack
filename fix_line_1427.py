#!/usr/bin/env python3

with open('/home/LetoBlack/app/callcenter/callcenter.py', 'r') as f:
    lines = f.readlines()

# Печатаем контекст вокруг строки 1427
print("Контекст до исправления:")
for i in range(max(0, 1425-2), min(len(lines), 1427+5)):
    print(f"{i+1}: {lines[i]}", end="")

# Проверяем строку 1426 для получения правильного уровня отступа
if len(lines) > 1426:
    if "if report_type ==" in lines[1426]:
        # Определяем правильный отступ для if блока
        base_indent = len(lines[1426]) - len(lines[1426].lstrip())
        if_indent = base_indent + 4  # Внутри if блока добавляем 4 пробела
        
        # Исправляем строку 1427
        content = lines[1426].strip()
        if_line = " " * base_indent + content + "\n"
        lines[1426] = if_line
        
        content = lines[1427].strip()
        report_title_line = " " * if_indent + content + "\n"
        lines[1427] = report_title_line
        
        # Проверяем и исправляем следующие строки, если они также должны быть внутри if блока
        for i in range(1428, 1442):
            if i < len(lines):
                if "elif" in lines[i] or "else" in lines[i]:
                    break  # Достигли конца if блока
                
                # Проверяем, не содержит ли строка другой if
                if "if" in lines[i] and "elif" not in lines[i]:
                    # Это вложенный if, индентация должна быть сохранена относительно
                    continue
                
                if lines[i].strip() and not lines[i].strip().startswith("#"):
                    current_indent = len(lines[i]) - len(lines[i].lstrip())
                    if current_indent < if_indent:
                        content = lines[i].strip()
                        lines[i] = " " * if_indent + content + "\n"
        
        print("\nИсправлены строки внутри if блока, начиная с 1427")

# Сохраняем исправленный файл
with open('/home/LetoBlack/app/callcenter/callcenter.py', 'w') as f:
    f.writelines(lines)

print("\nПосле исправления:")
with open('/home/LetoBlack/app/callcenter/callcenter.py', 'r') as f:
    fixed_lines = f.readlines()
    for i in range(max(0, 1425-2), min(len(fixed_lines), 1427+5)):
        print(f"{i+1}: {fixed_lines[i]}", end="") 