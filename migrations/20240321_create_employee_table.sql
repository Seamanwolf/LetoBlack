-- Создаем таблицу Employee
CREATE TABLE IF NOT EXISTS Employee (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    position_id INT,
    department_id INT,
    hire_date DATE NOT NULL,
    salary DECIMAL(10, 2),
    status ENUM('active', 'fired', 'vacation') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User(id) ON DELETE CASCADE,
    FOREIGN KEY (position_id) REFERENCES Position(id) ON DELETE SET NULL,
    FOREIGN KEY (department_id) REFERENCES Department(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Добавляем индекс для быстрого поиска по статусу
CREATE INDEX idx_employee_status ON Employee(status);

-- Добавляем индекс для поиска по отделу
CREATE INDEX idx_employee_department ON Employee(department_id); 