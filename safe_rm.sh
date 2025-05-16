#!/bin/bash

# Путь к корзине
TRASH_DIR="$HOME/.local/share/Trash/files"
TRASH_INFO="$HOME/.local/share/Trash/info"

# Создаем директории, если их нет
mkdir -p "$TRASH_DIR" "$TRASH_INFO"

# Функция для генерации уникального имени файла
generate_unique_name() {
    local original_name="$1"
    local counter=1
    local new_name="$original_name"
    
    while [ -e "$TRASH_DIR/$new_name" ]; do
        new_name="${original_name}.$counter"
        counter=$((counter + 1))
    done
    
    echo "$new_name"
}

# Обработка каждого аргумента
for file in "$@"; do
    if [ -e "$file" ]; then
        # Получаем полный путь к файлу
        full_path=$(readlink -f "$file")
        
        # Получаем имя файла
        file_name=$(basename "$file")
        
        # Генерируем уникальное имя для файла в корзине
        unique_name=$(generate_unique_name "$file_name")
        
        # Создаем файл с информацией о перемещенном файле
        cat > "$TRASH_INFO/${unique_name}.trashinfo" << EOF
[Trash Info]
Path=$full_path
DeletionDate=$(date +%Y-%m-%dT%H:%M:%S)
EOF
        
        # Перемещаем файл в корзину
        mv "$file" "$TRASH_DIR/$unique_name"
        
        echo "Файл '$file' перемещен в корзину"
    else
        echo "Ошибка: файл '$file' не существует"
    fi
done 