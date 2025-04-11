-- Добавление внешнего ключа leader_id в таблицу Department
ALTER TABLE Department
ADD CONSTRAINT fk_department_leader
FOREIGN KEY (leader_id) REFERENCES Employee(id) ON DELETE SET NULL; 