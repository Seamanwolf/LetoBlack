-- Скрипт для исправления дублирующихся префиксов +7 в номерах телефонов
-- Создаём временную таблицу для логирования изменений
CREATE TEMPORARY TABLE phone_number_changes (
    id INT,
    old_phone_number VARCHAR(20),
    new_phone_number VARCHAR(20)
);

-- Находим номера с двойным префиксом +7+7 и записываем их в лог
INSERT INTO phone_number_changes (id, old_phone_number, new_phone_number)
SELECT id, phone_number, CONCAT('+7', SUBSTRING(phone_number, 4))
FROM corp_numbers
WHERE phone_number LIKE '+7+7%';

-- Выводим список изменений, которые будут сделаны
SELECT * FROM phone_number_changes;

-- Обновляем номера с двойным префиксом +7+7
UPDATE corp_numbers
SET phone_number = CONCAT('+7', SUBSTRING(phone_number, 4))
WHERE phone_number LIKE '+7+7%';

-- Проверяем обновленные номера
SELECT id, phone_number
FROM corp_numbers
WHERE id IN (SELECT id FROM phone_number_changes);

-- Очищаем временную таблицу
DROP TEMPORARY TABLE IF EXISTS phone_number_changes; 