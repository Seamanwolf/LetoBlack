-- Перенос должностей из таблицы User в таблицу Position
INSERT INTO Position (name, description, created_at, updated_at)
SELECT DISTINCT position, '', NOW(), NOW()
FROM User
WHERE position IS NOT NULL AND position != ''
AND position NOT IN (SELECT name FROM Position); 