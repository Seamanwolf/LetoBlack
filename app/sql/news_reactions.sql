-- Таблица для реакций на новости
CREATE TABLE IF NOT EXISTS NewsReactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    news_id INT NOT NULL,
    user_id INT NOT NULL,
    reaction_type ENUM('positive', 'neutral', 'negative') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (news_id) REFERENCES News(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES User(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_news_reaction (news_id, user_id)
);

-- Индексы для быстрого поиска
CREATE INDEX idx_news_reactions_news_id ON NewsReactions(news_id);
CREATE INDEX idx_news_reactions_user_id ON NewsReactions(user_id);
CREATE INDEX idx_news_reactions_type ON NewsReactions(reaction_type); 