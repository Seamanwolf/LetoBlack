-- Создание таблицы для хранения рейтингов сотрудников
CREATE TABLE IF NOT EXISTS `Rating` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `quarterly_rating` DECIMAL(3,1) DEFAULT 0.0,
  `avg_deals` INT DEFAULT 0,
  `properties` INT DEFAULT 0,
  `scripts` INT DEFAULT 0,
  `crm_cards` INT DEFAULT 0,
  `avg_score` DECIMAL(3,1) GENERATED ALWAYS AS (
    (quarterly_rating + avg_deals + properties + scripts + crm_cards) / 5
  ) STORED,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_id` (`user_id`),
  CONSTRAINT `fk_rating_user_id` FOREIGN KEY (`user_id`) REFERENCES `User`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci; 