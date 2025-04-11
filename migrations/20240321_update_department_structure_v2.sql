-- Добавляем колонку location_id в таблицу Department
ALTER TABLE Department ADD COLUMN location_id INT;

-- Добавляем внешний ключ для location_id
ALTER TABLE Department ADD CONSTRAINT fk_department_location 
FOREIGN KEY (location_id) REFERENCES Location(id);

-- Добавляем колонку leader_id в таблицу Department
ALTER TABLE Department ADD COLUMN leader_id INT;

-- Добавляем внешний ключ для leader_id
ALTER TABLE Department ADD CONSTRAINT fk_department_leader 
FOREIGN KEY (leader_id) REFERENCES User(id);

-- Добавляем колонки created_at и updated_at
ALTER TABLE Department ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE Department ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- Добавляем колонку location_id в таблицу Department
ALTER TABLE Department ADD COLUMN location_id INT;
ALTER TABLE Department ADD CONSTRAINT fk_department_location FOREIGN KEY (location_id) REFERENCES Location(id);

-- Восстанавливаем внешние ключи
ALTER TABLE Location ADD CONSTRAINT Location_ibfk_3 FOREIGN KEY (department_id) REFERENCES Department(id);
ALTER TABLE Room ADD CONSTRAINT Room_ibfk_1 FOREIGN KEY (department_id) REFERENCES Department(id); 