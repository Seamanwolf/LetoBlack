-- Добавление полей name и address в таблицу Location
ALTER TABLE Location
ADD COLUMN name VARCHAR(255) AFTER id,
ADD COLUMN address VARCHAR(255) AFTER name; 