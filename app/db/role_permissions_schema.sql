-- Таблица модулей системы
CREATE TABLE IF NOT EXISTS `Modules` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL UNIQUE COMMENT 'Системное имя модуля (hr, reception, etc)',
    `display_name` VARCHAR(100) NOT NULL COMMENT 'Отображаемое название модуля (HR, Ресепшн, etc)',
    `description` TEXT COMMENT 'Описание модуля',
    `route` VARCHAR(100) COMMENT 'Базовый маршрут модуля',
    `icon` VARCHAR(100) COMMENT 'Иконка модуля для меню',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица разрешений ролей на модули
CREATE TABLE IF NOT EXISTS `RolePermissions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `role_id` INT NOT NULL,
    `module_id` INT NOT NULL,
    `can_view` BOOLEAN DEFAULT 0 COMMENT 'Может просматривать',
    `can_create` BOOLEAN DEFAULT 0 COMMENT 'Может создавать',
    `can_edit` BOOLEAN DEFAULT 0 COMMENT 'Может редактировать',
    `can_delete` BOOLEAN DEFAULT 0 COMMENT 'Может удалять',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`role_id`) REFERENCES `Roles`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`module_id`) REFERENCES `Modules`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `unique_role_module` (`role_id`, `module_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Заполняем таблицу модулей системы
INSERT INTO `Modules` (`name`, `display_name`, `description`, `route`) VALUES
('admin', 'Администрирование', 'Модуль администрирования системы', 'admin'),
('callcenter', 'Колл-центр', 'Управление колл-центром', 'callcenter'),
('hr', 'HR', 'Управление персоналом', 'hr'),
('reception', 'Ресепшн', 'Модуль ресепшн', 'reception'),
('sales', 'Продажи', 'Модуль продаж', 'sales'),
('finance', 'Финансы', 'Модуль финансов', 'finance'),
('reporting', 'Отчеты', 'Модуль отчетов', 'reporting'),
('user', 'Пользователи', 'Модуль управления пользователями', 'userlist');

-- Добавляем полный доступ для роли admin ко всем модулям
INSERT INTO `RolePermissions` (`role_id`, `module_id`, `can_view`, `can_create`, `can_edit`, `can_delete`)
SELECT 
    (SELECT `id` FROM `Roles` WHERE `name` = 'admin'), 
    `id`, 
    1, 1, 1, 1
FROM `Modules`;

-- Добавляем доступ к модулю callcenter для роли operator
INSERT INTO `RolePermissions` (`role_id`, `module_id`, `can_view`, `can_create`, `can_edit`, `can_delete`)
VALUES (
    (SELECT `id` FROM `Roles` WHERE `name` = 'operator'),
    (SELECT `id` FROM `Modules` WHERE `name` = 'callcenter'),
    1, 1, 0, 0
);

-- Добавляем доступ к модулю user и reporting для роли leader
INSERT INTO `RolePermissions` (`role_id`, `module_id`, `can_view`, `can_create`, `can_edit`, `can_delete`)
VALUES 
(
    (SELECT `id` FROM `Roles` WHERE `name` = 'leader'),
    (SELECT `id` FROM `Modules` WHERE `name` = 'user'),
    1, 1, 1, 0
),
(
    (SELECT `id` FROM `Roles` WHERE `name` = 'leader'),
    (SELECT `id` FROM `Modules` WHERE `name` = 'reporting'),
    1, 1, 1, 0
);

-- Ограничиваем системные роли от изменения
ALTER TABLE `Roles` ADD COLUMN `is_system` BOOLEAN DEFAULT 0 COMMENT 'Системная роль (нельзя удалить)';

-- Обновляем системные роли
UPDATE `Roles` SET `is_system` = 1 WHERE `name` IN ('admin', 'leader', 'operator', 'user');

-- Добавляем тип роли (для бэк-офиса)
ALTER TABLE `Roles` ADD COLUMN `role_type` ENUM('system', 'backoffice', 'custom') DEFAULT 'custom' COMMENT 'Тип роли';

-- Обновляем типы ролей
UPDATE `Roles` SET `role_type` = 'system' WHERE `is_system` = 1;
UPDATE `Roles` SET `role_type` = 'backoffice' WHERE `name` = 'backoffice'; 