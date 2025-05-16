import ast
import sys

try:
    with open('/home/LetoBlack/app/callcenter/callcenter.py', 'r') as f:
        content = f.read()
        try:
            ast.parse(content)
            print('Файл имеет правильный синтаксис Python')
        except SyntaxError as e:
            line_num = e.lineno
            print(f'Ошибка синтаксиса в строке {line_num}: {e}')
            # Показываем проблемную строку и несколько строк вокруг неё
            lines = content.split('\n')
            start = max(0, line_num - 3)
            end = min(len(lines), line_num + 3)
            for i in range(start, end):
                prefix = '> ' if i+1 == line_num else '  '
                print(f'{prefix}{i+1}: {lines[i]}')
except Exception as e:
    print(f'Произошла ошибка при чтении файла: {e}') 