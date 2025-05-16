-- Таблица для хранения дополнительных данных о сотрудниках
CREATE TABLE IF NOT EXISTS EmployeeDetails (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    has_documents TINYINT DEFAULT 0,
    has_rr TINYINT DEFAULT 0,
    has_site TINYINT DEFAULT 0,
    notes TEXT,
    previous_number VARCHAR(20),
    UNIQUE KEY (employee_id)
);

-- Таблица для хранения фотографий сотрудников
CREATE TABLE IF NOT EXISTS EmployeePhotos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    photo_url VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY (employee_id)
);

-- Таблица для истории изменений пользователей
CREATE TABLE IF NOT EXISTS `UserHistory` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `changed_field` varchar(255) NOT NULL,
  `old_value` text,
  `new_value` text,
  `changed_by` int(11),
  `changed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `changed_by` (`changed_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Таблица для истории номеров телефонов
CREATE TABLE IF NOT EXISTS `NumberHistory` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `old_number` varchar(20),
  `new_number` varchar(20),
  `note` text,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Добавляем колонку в таблицу Candidates для хранения личного телефона, если еще не существует
ALTER TABLE Candidates 
ADD COLUMN IF NOT EXISTS personal_phone VARCHAR(20) DEFAULT NULL;

-- Добавляем индексы для ускорения поиска
ALTER TABLE UserHistory 
ADD INDEX IF NOT EXISTS idx_user_id (user_id);

-- Проверка существования столбцов и их добавление при необходимости
-- Добавление столбца changed_at в UserHistory, если он не существует
SET @query = (
  SELECT IF(
    NOT EXISTS(
      SELECT * FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'UserHistory'
      AND COLUMN_NAME = 'changed_at'
    ),
    'ALTER TABLE UserHistory ADD COLUMN changed_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP',
    'SELECT 1'
  )
);
PREPARE stmt FROM @query;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Добавление столбца old_number в NumberHistory, если он не существует
SET @query = (
  SELECT IF(
    NOT EXISTS(
      SELECT * FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'NumberHistory'
      AND COLUMN_NAME = 'old_number'
    ),
    'ALTER TABLE NumberHistory ADD COLUMN old_number varchar(20)',
    'SELECT 1'
  )
);
PREPARE stmt FROM @query;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Добавление столбца note в NumberHistory, если он не существует
SET @query = (
  SELECT IF(
    NOT EXISTS(
      SELECT * FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'NumberHistory'
      AND COLUMN_NAME = 'note'
    ),
    'ALTER TABLE NumberHistory ADD COLUMN note text',
    'SELECT 1'
  )
);
PREPARE stmt FROM @query;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Данный SQL-скрипт создаёт только те таблицы и поля, которые отсутствуют
-- Примечание: Многие поля, которые планировалось добавить в EmployeeDetails,
-- уже существуют в таблице User (documents, rr, site, notes и др.) 