-- Добавление колонки name в таблицу Location
ALTER TABLE Location
ADD COLUMN name VARCHAR(255) NOT NULL AFTER id; 