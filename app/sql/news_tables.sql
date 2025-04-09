-- Таблица для хранения новостей
CREATE TABLE IF NOT EXISTS News (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    image VARCHAR(255) NULL,
    author_id INT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NULL,
    FOREIGN KEY (author_id) REFERENCES User(id)
);

-- Таблица для связи новостей с ролями (кому видна новость)
CREATE TABLE IF NOT EXISTS NewsRoles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    news_id INT NOT NULL,
    role_id INT NOT NULL,
    FOREIGN KEY (news_id) REFERENCES News(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES Role(id) ON DELETE CASCADE,
    UNIQUE KEY news_role_unique (news_id, role_id)
);

-- Индексы для ускорения запросов
CREATE INDEX idx_news_category ON News(category);
CREATE INDEX idx_news_created_at ON News(created_at);
CREATE INDEX idx_news_roles_role_id ON NewsRoles(role_id); 