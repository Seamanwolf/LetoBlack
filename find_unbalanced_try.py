import re

def check_try_except_balance(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
        lines = content.split('\n')
        
        # Ищем все строки с отдельно стоящими try:, except: и finally:
        try_lines = []
        except_lines = []
        finally_lines = []
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.match(r'^try\s*:$', stripped):
                try_lines.append(i)
            elif re.match(r'^except\b', stripped):
                except_lines.append(i)
            elif re.match(r'^finally\s*:$', stripped):
                finally_lines.append(i)
        
        # Простая проверка: количество try должно быть >= количеству except + finally блоков
        if len(try_lines) < len(except_lines) + len(finally_lines):
            print(f"Дисбаланс: найдено {len(try_lines)} try блоков, {len(except_lines)} except блоков и {len(finally_lines)} finally блоков")
        
        # Выводим все найденные блоки
        print(f"try блоки: {try_lines}")
        print(f"except блоки: {except_lines}")
        print(f"finally блоки: {finally_lines}")
        
        # Проверяем правильную последовательность
        for try_line in try_lines:
            # Ищем ближайший except или finally после try
            found_handler = False
            for except_line in except_lines:
                if except_line > try_line:
                    found_handler = True
                    break
            if not found_handler:
                for finally_line in finally_lines:
                    if finally_line > try_line:
                        found_handler = True
                        break
            
            if not found_handler:
                print(f"Незакрытый try в строке {try_line}")
                # Печатаем контекст вокруг проблемного блока
                start = max(0, try_line - 3)
                end = min(len(lines), try_line + 7)
                print("Контекст:")
                for i in range(start, end):
                    print(f"{i+1}: {lines[i]}")

# Проверяем файл
check_try_except_balance('/home/LetoBlack/app/callcenter/callcenter.py') 