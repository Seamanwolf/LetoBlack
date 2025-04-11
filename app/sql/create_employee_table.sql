-- Создание таблицы сотрудников
CREATE TABLE IF NOT EXISTS Employee (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    position_id INT,
    department_id INT,
    hire_date DATE NOT NULL,
    fire_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User(id) ON DELETE CASCADE,
    FOREIGN KEY (position_id) REFERENCES Position(id) ON DELETE SET NULL,
    FOREIGN KEY (department_id) REFERENCES Department(id) ON DELETE SET NULL
); 