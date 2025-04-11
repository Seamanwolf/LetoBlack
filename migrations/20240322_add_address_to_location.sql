-- Добавление колонки address в таблицу Location
ALTER TABLE Location
ADD COLUMN address VARCHAR(255) NOT NULL AFTER name; 