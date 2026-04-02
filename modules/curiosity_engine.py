import os
import random
import logging
import sqlite3
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger("atena.curiosity")

class CuriosityEngine:
    """
    Hacker Recon 2.0: Sistema de Curiosidade Intrínseca.
    Usa um loop de recompensa para decidir quais tópicos explorar
    baseado na novidade e utilidade para o DNA atual.
    """
    def __init__(self, db_path: str = "atena_evolution/knowledge/knowledge.db"):
        self.db_path = db_path
        self._init_db()
        self.exploration_history = []
        
    def _init_db(self):
        """Garante que as tabelas de curiosidade existam."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS curiosity_topics (
                topic TEXT PRIMARY KEY,
                interest_score REAL DEFAULT 1.0,
                last_explored DATETIME,
                discovery_count INTEGER DEFAULT 0,
                reward_sum REAL DEFAULT 0.0
            )
        """)
        conn.commit()
        conn.close()

    def get_next_topic(self) -> str:
        """Decide o próximo tópico para exploração usando estratégia Epsilon-Greedy."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 20% exploração aleatória, 80% exploração baseada em interesse
        if random.random() < 0.2:
            topics = ["advanced python optimization", "neural architecture search", 
                      "autonomous agents", "self-modifying code", "distributed systems"]
            topic = random.choice(topics)
        else:
            cursor.execute("SELECT topic FROM curiosity_topics ORDER BY interest_score DESC LIMIT 5")
            results = cursor.fetchall()
            if not results:
                topic = "artificial general intelligence"
            else:
                topic = random.choice([r[0] for r in results])
        
        conn.close()
        return topic

    def update_reward(self, topic: str, reward: float):
        """Atualiza o interesse no tópico baseado na recompensa recebida (ex: novas funções úteis)."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO curiosity_topics (topic, interest_score, last_explored, discovery_count, reward_sum)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(topic) DO UPDATE SET
                reward_sum = reward_sum + EXCLUDED.reward_sum,
                discovery_count = discovery_count + 1,
                interest_score = (reward_sum + EXCLUDED.reward_sum) / (discovery_count + 1),
                last_explored = EXCLUDED.last_explored
        """, (topic, reward, datetime.now().isoformat(), reward))
        conn.commit()
        conn.close()
        logger.info(f"[Curiosity] Tópico '{topic}' atualizado com recompensa {reward:.2f}")

    def perceive_world(self) -> List[Dict[str, Any]]:
        """Simula a percepção de novas tendências para alimentar a curiosidade."""
        # Stub para integração com NewsAPI ou GitHub Trends
        trends = [
            {"topic": "transformers optimization", "source": "arXiv"},
            {"topic": "rust for python extensions", "source": "GitHub"},
            {"topic": "vector databases performance", "source": "TechNews"}
        ]
        for trend in trends:
            self.update_reward(trend['topic'], 0.5) # Interesse inicial
        return trends

# Instância global
curiosity = CuriosityEngine()
