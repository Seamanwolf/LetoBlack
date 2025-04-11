-- Обновление структуры таблицы Location
-- Удаление полей city_id, floor_id, department_id и room_id

-- Сначала удаляем внешние ключи
ALTER TABLE Location
DROP FOREIGN KEY location_ibfk_1,
DROP FOREIGN KEY location_ibfk_2,
DROP FOREIGN KEY location_ibfk_3,
DROP FOREIGN KEY location_ibfk_4;

-- Затем удаляем колонки
ALTER TABLE Location
DROP COLUMN city_id,
DROP COLUMN floor_id,
DROP COLUMN department_id,
DROP COLUMN room_id; 