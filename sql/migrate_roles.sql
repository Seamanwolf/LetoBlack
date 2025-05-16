-- Создаем необходимые таблицы
CREATE TABLE IF NOT EXISTS `Role` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(50) NOT NULL UNIQUE COMMENT 'Название роли',
  `description` TEXT COMMENT 'Описание роли',
  `is_admin` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Флаг для роли администратора',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Создаем таблицу Module для разделов системы
CREATE TABLE IF NOT EXISTS `Module` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(50) NOT NULL UNIQUE COMMENT 'Название модуля/раздела',
  `description` TEXT COMMENT 'Описание модуля',
  `url_path` VARCHAR(100) COMMENT 'URL-путь модуля',
  `icon` VARCHAR(50) COMMENT 'Иконка для меню',
  `order` INT DEFAULT 0 COMMENT 'Порядок отображения',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'Активен ли модуль',
  `parent_id` INT NULL COMMENT 'ID родительского модуля для подразделов',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (`parent_id`) REFERENCES `Module`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Создаем таблицу RolePermission для разрешений
CREATE TABLE IF NOT EXISTS `RolePermission` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `role_id` INT NOT NULL,
  `module_id` INT NOT NULL,
  `can_view` TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'Право на просмотр',
  `can_edit` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Право на редактирование',
  `can_create` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Право на создание',
  `can_delete` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Право на удаление',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (`role_id`) REFERENCES `Role`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`module_id`) REFERENCES `Module`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `unique_role_module` (`role_id`, `module_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Создаем таблицу UserRole для связи пользователей с ролями
CREATE TABLE IF NOT EXISTS `UserRole` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `role_id` INT NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (`user_id`) REFERENCES `User`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`role_id`) REFERENCES `Role`(`id`) ON DELETE CASCADE,
  UNIQUE KEY `unique_user_role` (`user_id`, `role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Заполняем таблицу Role существующими ролями из таблицы User
INSERT INTO `Role` (`name`, `description`, `is_admin`)
VALUES 
('Администратор', 'Полный доступ ко всем разделам системы', 1),
('Руководитель', 'Управление отделом и доступ к отчетам', 0),
('Администратор КЦ', 'Управление контакт-центром', 1),
('Пользователь', 'Базовые права доступа', 0),
('Бэк-офис', 'Доступ к документам и заявкам', 0),
('Оператор', 'Работа с клиентами', 0);

-- Создаем соответствие между старыми и новыми ролями
CREATE TEMPORARY TABLE role_mapping (
  old_role VARCHAR(20),
  new_role_id INT
);

INSERT INTO role_mapping VALUES
('admin', 1),       -- admin -> Администратор
('leader', 2),      -- leader -> Руководитель
('cc_admin', 3),    -- cc_admin -> Администратор КЦ
('user', 4),        -- user -> Пользователь
('backoffice', 5),  -- backoffice -> Бэк-офис
('operator', 6);    -- operator -> Оператор

-- Заполняем таблицу модулей основными разделами системы
INSERT INTO `Module` (`name`, `description`, `url_path`, `icon`, `order`, `is_active`)
VALUES
('Дашборд', 'Главная страница системы', '/dashboard', 'fa-home', 1, 1),
('Новости', 'Управление новостями', '/news', 'fa-newspaper', 2, 1),
('Рейтинг', 'Рейтинг брокеров', '/rating', 'fa-chart-line', 3, 1),
('Персонал', 'Управление сотрудниками', '/personnel', 'fa-users', 4, 1),
('Настройки', 'Настройки системы', '/admin/settings', 'fa-cog', 5, 1),
('Колл-центр', 'Управление колл-центром', '/vats', 'fa-phone', 6, 1);

-- Делаем соответствие между пользователями и ролями на основе существующего поля role
INSERT INTO `UserRole` (`user_id`, `role_id`)
SELECT u.id, rm.new_role_id
FROM `User` u
JOIN role_mapping rm ON u.role = rm.old_role;

-- Добавляем права для роли Администратор (доступ ко всему)
INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
SELECT 1, id, 1, 1, 1, 1 FROM `Module`;

-- Добавляем права для роли Руководитель (доступ к дашборду, новостям, рейтингу, персоналу)
INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
SELECT 2, id, 1, 1, 1, 0 FROM `Module` WHERE `name` IN ('Дашборд', 'Новости', 'Рейтинг', 'Персонал');

-- Добавляем права для роли Администратор КЦ (доступ к дашборду, колл-центру, настройкам колл-центра)
INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
SELECT 3, id, 1, 1, 1, 1 FROM `Module` WHERE `name` IN ('Дашборд', 'Колл-центр');
INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
SELECT 3, id, 1, 0, 0, 0 FROM `Module` WHERE `name` IN ('Новости');

-- Добавляем права для роли Пользователь (базовый доступ)
INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
SELECT 4, id, 1, 0, 0, 0 FROM `Module` WHERE `name` IN ('Дашборд', 'Новости');

-- Добавляем права для роли Бэк-офис
INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
SELECT 5, id, 1, 1, 1, 0 FROM `Module` WHERE `name` IN ('Дашборд', 'Новости');

-- Добавляем права для роли Оператор
INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
SELECT 6, id, 1, 0, 0, 0 FROM `Module` WHERE `name` IN ('Дашборд', 'Колл-центр');

-- Удаляем временную таблицу
DROP TEMPORARY TABLE role_mapping; 