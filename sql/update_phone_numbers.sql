USE Brokers;

-- Обновляем corp_phone, добавляя к существующим значениям номера из Phone
UPDATE User 
SET corp_phone = CONCAT(
    CASE 
        WHEN corp_phone IS NOT NULL AND corp_phone != '' 
        THEN CONCAT(corp_phone, ', ') 
        ELSE '' 
    END,
    Phone
)
WHERE Phone IS NOT NULL AND Phone != '';

-- Очищаем поле Phone
UPDATE User 
SET Phone = NULL 
WHERE Phone IS NOT NULL; 