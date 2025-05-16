#!/bin/bash

TRASH_DIR="$HOME/.local/share/Trash/files"
TRASH_INFO="$HOME/.local/share/Trash/info"

# Проверяем наличие файлов в корзине
if [ -z "$(ls -A $TRASH_DIR)" ]; then
    echo "Корзина пуста"
    exit 0
fi

# Выводим список файлов в корзине
echo "Файлы в корзине:"
ls -l "$TRASH_DIR" | awk '{print NR, $9}'

# Запрашиваем номер файла для восстановления
read -p "Введите номер файла для восстановления (или 'q' для выхода): " choice

if [ "$choice" = "q" ]; then
    exit 0
fi

# Получаем имя файла по номеру
file_to_restore=$(ls "$TRASH_DIR" | sed -n "${choice}p")

if [ -z "$file_to_restore" ]; then
    echo "Неверный номер файла"
    exit 1
fi

# Читаем информацию о файле
info_file="$TRASH_INFO/${file_to_restore}.trashinfo"
if [ -f "$info_file" ]; then
    original_path=$(grep "^Path=" "$info_file" | cut -d= -f2)
    
    # Проверяем существование оригинальной директории
    original_dir=$(dirname "$original_path")
    if [ ! -d "$original_dir" ]; then
        mkdir -p "$original_dir"
    fi
    
    # Восстанавливаем файл
    mv "$TRASH_DIR/$file_to_restore" "$original_path"
    rm "$info_file"
    
    echo "Файл восстановлен в: $original_path"
else
    echo "Ошибка: информация о файле не найдена"
fi 