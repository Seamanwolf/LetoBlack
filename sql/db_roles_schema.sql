-- Таблица ролей
CREATE TABLE IF NOT EXISTS `Role` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(50) NOT NULL UNIQUE COMMENT 'Название роли',
  `description` TEXT COMMENT 'Описание роли',
  `is_admin` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Флаг для роли администратора',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Таблица модулей/разделов системы
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

-- Таблица разрешений для ролей на модули
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

-- Таблица для связи пользователей с ролями
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

-- Начальные данные: основные роли
INSERT INTO `Role` (`name`, `description`, `is_admin`) VALUES
('Администратор', 'Полный доступ ко всем разделам системы', 1),
('Контент-менеджер', 'Управление новостями и контентом', 0),
('Руководитель отдела продаж', 'Доступ к дашборду руководителя и отчетам', 0),
('Брокер', 'Базовый доступ для брокеров', 0);

-- Начальные данные: основные модули
INSERT INTO `Module` (`name`, `description`, `url_path`, `icon`, `order`, `is_active`) VALUES
('Дашборд', 'Главная страница системы', '/dashboard', 'fa-home', 1, 1),
('Новости', 'Управление новостями', '/news', 'fa-newspaper', 2, 1),
('Рейтинг', 'Рейтинг брокеров', '/rating', 'fa-chart-line', 3, 1),
('Персонал', 'Управление сотрудниками', '/personnel', 'fa-users', 4, 1),
('Настройки', 'Настройки системы', '/admin/settings', 'fa-cog', 5, 1);

-- Права для роли Администратор (доступ ко всему)
INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
SELECT 1, id, 1, 1, 1, 1 FROM `Module`;

-- Права для роли Контент-менеджер (только новости)
INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
SELECT 2, id, 1, 1, 1, 1 FROM `Module` WHERE `name` = 'Новости';
INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
SELECT 2, id, 1, 0, 0, 0 FROM `Module` WHERE `name` = 'Дашборд';

-- Права для роли Руководитель отдела продаж
INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
SELECT 3, id, 1, 0, 0, 0 FROM `Module` WHERE `name` IN ('Дашборд', 'Рейтинг');

-- Права для роли Брокер
INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
SELECT 4, id, 1, 0, 0, 0 FROM `Module` WHERE `name` IN ('Дашборд', 'Новости'); 