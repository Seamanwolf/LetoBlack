-- Создание таблицы ролей
CREATE TABLE IF NOT EXISTS `Roles` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(50) NOT NULL,
  `display_name` VARCHAR(100) NOT NULL,
  `description` TEXT,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_role_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Заполнение таблицы ролей
INSERT INTO `Roles` (`name`, `display_name`, `description`) VALUES
('admin', 'Администратор', 'Полный доступ ко всем функциям системы'),
('leader', 'Руководитель', 'Управление отделом и сотрудниками'),
('user', 'Пользователь', 'Базовый доступ к функциям системы'),
('operator', 'Оператор колл-центра', 'Доступ к функциям колл-центра'),
('backoffice', 'Бэк-офис', 'Административные функции');

-- Создание таблицы для настроек колл-центра
CREATE TABLE IF NOT EXISTS `CallCenterSettings` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `ukc_kc` ENUM('УКЦ', 'КЦ') DEFAULT 'УКЦ',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Создание таблицы для отслеживания активности пользователей
CREATE TABLE IF NOT EXISTS `UserActivity` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `status` ENUM('online', 'offline', 'away', 'busy') DEFAULT 'offline',
  `last_activity` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_id` (`user_id`),
  INDEX `idx_status` (`status`),
  INDEX `idx_last_activity` (`last_activity`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Добавление колонки role_id в таблицу User
ALTER TABLE `User` ADD COLUMN `role_id` INT NULL AFTER `role`;

-- Обновление role_id на основе существующего поля role
UPDATE `User` SET `role_id` = (SELECT `id` FROM `Roles` WHERE `name` = `User`.`role`);

-- Миграция данных ukc_kc для операторов колл-центра
INSERT INTO `CallCenterSettings` (`user_id`, `ukc_kc`)
SELECT `id`, `ukc_kc` FROM `User` WHERE `role` = 'operator';

-- Миграция данных статуса пользователей
INSERT INTO `UserActivity` (`user_id`, `status`, `last_activity`)
SELECT `id`,
       CASE
           WHEN `status` IS NULL OR `status` = '' THEN 'offline'
           WHEN `status` = 'Онлайн' THEN 'online'
           WHEN `status` = 'Офлайн' THEN 'offline'
           ELSE 'offline'
       END,
       COALESCE(`last_active`, NOW())
FROM `User`;

-- Добавление внешнего ключа к таблице User
ALTER TABLE `User` ADD CONSTRAINT `fk_user_role_id` FOREIGN KEY (`role_id`) REFERENCES `Roles`(`id`);

-- Добавление внешних ключей к новым таблицам
ALTER TABLE `CallCenterSettings` ADD CONSTRAINT `fk_call_center_user_id` FOREIGN KEY (`user_id`) REFERENCES `User`(`id`) ON DELETE CASCADE;
ALTER TABLE `UserActivity` ADD CONSTRAINT `fk_user_activity_user_id` FOREIGN KEY (`user_id`) REFERENCES `User`(`id`) ON DELETE CASCADE;

-- Представление для обратной совместимости
CREATE OR REPLACE VIEW `UserFullView` AS
SELECT
    u.id,
    u.login,
    u.password,
    u.full_name,
    u.Phone,
    u.department,
    u.department_id,
    r.name AS role,
    u.role_id,
    c.ukc_kc,
    u.hire_date,
    u.fire_date,
    u.fired,
    a.status,
    a.last_activity AS last_active,
    u.personal_email,
    u.pc_login,
    u.pc_password,
    u.birth_date,
    u.position,
    u.office,
    u.corp_phone
FROM `User` u
LEFT JOIN `Roles` r ON u.role_id = r.id
LEFT JOIN `CallCenterSettings` c ON u.id = c.user_id
LEFT JOIN `UserActivity` a ON u.id = a.user_id;

-- После проверки работоспособности всех приложений, можно будет удалить ненужные столбцы из таблицы User:
-- ALTER TABLE `User` DROP COLUMN `ukc_kc`;
-- ALTER TABLE `User` DROP COLUMN `status`;
-- ALTER TABLE `User` DROP COLUMN `last_active`;
-- ALTER TABLE `User` DROP COLUMN `role`;

-- Создание новой таблицы для телефонных номеров
CREATE TABLE IF NOT EXISTS PhoneNumbers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    number VARCHAR(15) NOT NULL,
    type ENUM('corporate', 'personal', 'previous') NOT NULL,
    user_id INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User(id) ON DELETE CASCADE
);

-- Добавление новых колонок в таблицу User
ALTER TABLE User 
ADD COLUMN current_corp_phone_id INT NULL,
ADD COLUMN current_personal_phone_id INT NULL,
ADD COLUMN previous_phone_id INT NULL,
ADD FOREIGN KEY (current_corp_phone_id) REFERENCES PhoneNumbers(id),
ADD FOREIGN KEY (current_personal_phone_id) REFERENCES PhoneNumbers(id),
ADD FOREIGN KEY (previous_phone_id) REFERENCES PhoneNumbers(id);

-- Перенос существующих корпоративных номеров
INSERT INTO PhoneNumbers (number, type, user_id, is_active)
SELECT corp_phone, 'corporate', id, TRUE
FROM User
WHERE corp_phone IS NOT NULL AND corp_phone != '';

-- Обновление ссылок на корпоративные номера
UPDATE User u
JOIN PhoneNumbers pn ON u.id = pn.user_id AND pn.type = 'corporate'
SET u.current_corp_phone_id = pn.id
WHERE u.corp_phone IS NOT NULL AND u.corp_phone != '';

-- Перенос существующих личных номеров
INSERT INTO PhoneNumbers (number, type, user_id, is_active)
SELECT phone, 'personal', id, TRUE
FROM User
WHERE phone IS NOT NULL AND phone != '';

-- Обновление ссылок на личные номера
UPDATE User u
JOIN PhoneNumbers pn ON u.id = pn.user_id AND pn.type = 'personal'
SET u.current_personal_phone_id = pn.id
WHERE u.phone IS NOT NULL AND u.phone != '';

-- Перенос существующих предыдущих номеров
INSERT INTO PhoneNumbers (number, type, user_id, is_active)
SELECT previous_number, 'previous', id, TRUE
FROM User
WHERE previous_number IS NOT NULL AND previous_number != '';

-- Обновление ссылок на предыдущие номера
UPDATE User u
JOIN PhoneNumbers pn ON u.id = pn.user_id AND pn.type = 'previous'
SET u.previous_phone_id = pn.id
WHERE u.previous_number IS NOT NULL AND u.previous_number != '';

-- Создание индексов для оптимизации поиска
CREATE INDEX idx_phone_numbers_user_id ON PhoneNumbers(user_id);
CREATE INDEX idx_phone_numbers_type ON PhoneNumbers(type);
CREATE INDEX idx_phone_numbers_number ON PhoneNumbers(number);
CREATE INDEX idx_phone_numbers_is_active ON PhoneNumbers(is_active);

-- Создание представления для удобного получения текущих номеров
CREATE OR REPLACE VIEW UserPhoneNumbers AS
SELECT 
    u.id as user_id,
    u.full_name,
    corp_pn.number as corporate_number,
    pers_pn.number as personal_number,
    prev_pn.number as previous_number
FROM User u
LEFT JOIN PhoneNumbers corp_pn ON u.current_corp_phone_id = corp_pn.id
LEFT JOIN PhoneNumbers pers_pn ON u.current_personal_phone_id = pers_pn.id
LEFT JOIN PhoneNumbers prev_pn ON u.previous_phone_id = prev_pn.id;

-- Создание триггера для автоматического обновления updated_at
DELIMITER //
CREATE TRIGGER before_phone_numbers_update
BEFORE UPDATE ON PhoneNumbers
FOR EACH ROW
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END//
DELIMITER ;

-- Создание процедуры для добавления нового номера
DELIMITER //
CREATE PROCEDURE AddPhoneNumber(
    IN p_user_id INT,
    IN p_number VARCHAR(15),
    IN p_type ENUM('corporate', 'personal', 'previous')
)
BEGIN
    DECLARE new_phone_id INT;
    
    -- Деактивируем старый номер того же типа
    UPDATE PhoneNumbers 
    SET is_active = FALSE 
    WHERE user_id = p_user_id AND type = p_type AND is_active = TRUE;
    
    -- Добавляем новый номер
    INSERT INTO PhoneNumbers (number, type, user_id, is_active)
    VALUES (p_number, p_type, p_user_id, TRUE);
    
    SET new_phone_id = LAST_INSERT_ID();
    
    -- Обновляем ссылку в таблице User
    CASE p_type
        WHEN 'corporate' THEN
            UPDATE User SET current_corp_phone_id = new_phone_id WHERE id = p_user_id;
        WHEN 'personal' THEN
            UPDATE User SET current_personal_phone_id = new_phone_id WHERE id = p_user_id;
        WHEN 'previous' THEN
            UPDATE User SET previous_phone_id = new_phone_id WHERE id = p_user_id;
    END CASE;
END//
DELIMITER ; 