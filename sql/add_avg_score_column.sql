ALTER TABLE Rating
ADD COLUMN avg_score DECIMAL(10,2) GENERATED ALWAYS AS (
    (quarterly_rating + avg_deals + properties + scripts + crm_cards + call_duration + experience) / 7
) STORED; 