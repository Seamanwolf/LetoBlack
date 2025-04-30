import re

with open('/home/LetoBlack/app/callcenter/callcenter.py', 'r') as f:
    lines = f.readlines()

# Исправляем проблему на строке 990-991
if len(lines) >= 991:
    print("Строка 991 до исправления:", repr(lines[990]))
    if lines[990].strip() == "cursor.execute(query, params)":
        lines[990] = "        cursor.execute(query, params)\n"
        lines[991] = "        entries = cursor.fetchall()\n"
        print("Строка 991 после исправления:", repr(lines[990]))

# Сохраняем исправленный файл
with open('/home/LetoBlack/app/callcenter/callcenter_fixed.py', 'w') as f:
    f.writelines(lines)

print("Исправления внесены в файл callcenter_fixed.py") 