-- Обновление структуры таблицы Location
-- Удаление полей city_id, floor_id, department_id и room_id

-- Сначала удаляем внешние ключи, если они существуют
ALTER TABLE Location
DROP FOREIGN KEY IF EXISTS location_city_id_fk,
DROP FOREIGN KEY IF EXISTS location_floor_id_fk,
DROP FOREIGN KEY IF EXISTS location_department_id_fk,
DROP FOREIGN KEY IF EXISTS location_room_id_fk;

-- Затем удаляем колонки
ALTER TABLE Location
DROP COLUMN city_id,
DROP COLUMN floor_id,
DROP COLUMN department_id,
DROP COLUMN room_id;

-- Переименовываем колонку department_id в name
ALTER TABLE Location CHANGE department_id name VARCHAR(255) NOT NULL;

-- Добавляем колонки created_at и updated_at
ALTER TABLE Location ADD COLUMN created_at DATETIME DEFAULT NULL;
ALTER TABLE Location ADD COLUMN updated_at DATETIME DEFAULT NULL; 