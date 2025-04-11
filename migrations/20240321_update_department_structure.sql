-- Удаляем колонку floor_id из таблицы Department
ALTER TABLE Department DROP COLUMN floor_id;

-- Добавляем колонку location_id, если её нет
ALTER TABLE Department
ADD COLUMN location_id INT,
ADD CONSTRAINT fk_department_location
FOREIGN KEY (location_id) REFERENCES Location(id)
ON DELETE SET NULL;

-- Обновляем внешний ключ для leader_id, если его еще нет
ALTER TABLE Department
ADD CONSTRAINT fk_department_leader
FOREIGN KEY (leader_id) REFERENCES Employee(id)
ON DELETE SET NULL; 