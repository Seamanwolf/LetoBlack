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