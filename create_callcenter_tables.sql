-- Таблица для категорий звонков
CREATE TABLE IF NOT EXISTS CallCategories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(255) NOT NULL,
    `order` INT DEFAULT 0,
    archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для объектов
CREATE TABLE IF NOT EXISTS ObjectKC (
    id INT AUTO_INCREMENT PRIMARY KEY,
    object_name VARCHAR(255) NOT NULL,
    `order` INT DEFAULT 0,
    archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для источников
CREATE TABLE IF NOT EXISTS SourceKC (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_name VARCHAR(255) NOT NULL,
    `order` INT DEFAULT 0,
    archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для звонков
CREATE TABLE IF NOT EXISTS Calls (
    id INT AUTO_INCREMENT PRIMARY KEY,
    number VARCHAR(255) NOT NULL,
    category_id INT,
    timeline ENUM('daily', 'nighty') DEFAULT 'daily',
    hide ENUM('yes', 'no') DEFAULT 'no',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES CallCategories(id)
);

-- Таблица для активности операторов
CREATE TABLE IF NOT EXISTS OperatorActivity (
    id INT AUTO_INCREMENT PRIMARY KEY,
    operator_id INT NOT NULL,
    date DATE NOT NULL,
    active_time INT DEFAULT 0,
    last_active TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (operator_id) REFERENCES User(id)
);

-- Таблица для уведомлений
CREATE TABLE IF NOT EXISTS Notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    message TEXT NOT NULL,
    is_for_operator BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для связи пользователей с уведомлениями
CREATE TABLE IF NOT EXISTS UserNotifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    notification_id INT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User(id),
    FOREIGN KEY (notification_id) REFERENCES Notifications(id)
);

-- Таблица для черного списка
CREATE TABLE IF NOT EXISTS Blacklist (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    added_by INT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User(id),
    FOREIGN KEY (added_by) REFERENCES User(id)
);

-- Таблица для интеграций
CREATE TABLE IF NOT EXISTS Integrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    url TEXT,
    selected_fields JSON,
    last_synced_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для авторизации Google
CREATE TABLE IF NOT EXISTS GoogleAuth (
    id INT AUTO_INCREMENT PRIMARY KEY,
    token TEXT NOT NULL,
    refresh_token TEXT,
    token_uri VARCHAR(255),
    client_id VARCHAR(255),
    client_secret VARCHAR(255),
    scopes JSON,
    user_email VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для скоринга колл-центра
CREATE TABLE IF NOT EXISTS ScoringKC (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL,
    time TIME NOT NULL,
    broker_id INT NOT NULL,
    department_id VARCHAR(255),
    floor_id INT,
    object_id INT,
    source_id INT,
    client_id VARCHAR(255) NOT NULL,
    operator VARCHAR(255) NOT NULL,
    operator_id INT NOT NULL,
    status VARCHAR(50) DEFAULT 'transferred',
    operator_type ENUM('КЦ', 'УКЦ') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (broker_id) REFERENCES User(id),
    FOREIGN KEY (operator_id) REFERENCES User(id),
    FOREIGN KEY (floor_id) REFERENCES CallCategories(id),
    FOREIGN KEY (object_id) REFERENCES ObjectKC(id),
    FOREIGN KEY (source_id) REFERENCES SourceKC(id)
); 