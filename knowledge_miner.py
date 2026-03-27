# modules/knowledge_miner.py
"""
Módulo de mineração de conhecimento para Atena.
Coleta dados de múltiplas fontes e os integra ao banco de conhecimento.
"""

import os
import re
import time
import json
import logging
import sqlite3
import threading
import requests
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
import hashlib

# Tentar importar dependências opcionais
try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    import wikipedia
    HAS_WIKIPEDIA = True
except ImportError:
    HAS_WIKIPEDIA = False

try:
    from bs4 import BeautifulSoup
    HAS_BEAUTIFULSOUP = True
except ImportError:
    HAS_BEAUTIFULSOUP = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

try:
    import arxiv
    HAS_ARXIV = True
except ImportError:
    HAS_ARXIV = False

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

logger = logging.getLogger("atena.knowledge_miner")

# =============================================================
# 1. Configurações
# =============================================================

KNOWLEDGE_DB = "atena_evolution/knowledge/knowledge.db"
MINER_CACHE_DIR = Path("atena_evolution/knowledge/miner_cache")
MINER_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Fontes padrão
DEFAULT_NEWS_FEEDS = [
    "http://rss.cnn.com/rss/edition.rss",
    "http://feeds.bbci.co.uk/news/rss.xml",
    "https://feeds.npr.org/1001/rss.xml",
    "https://www.sciencedaily.com/rss/all.xml",
    "https://arxiv.org/rss/cs.AI"
]

DEFAULT_WIKI_CATEGORIES = ["Artificial intelligence", "Machine learning", "Python programming language", "Open source software"]

# =============================================================
# 2. Estruturas de dados
# =============================================================

@dataclass
class KnowledgeItem:
    """Representa um item de conhecimento extraído."""
    source: str
    title: str
    content: str
    url: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None
    tags: List[str] = None
    embedding: Optional[List[float]] = None
    hash: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.hash is None:
            self.hash = hashlib.sha256(f"{self.source}{self.title}{self.content[:500]}".encode()).hexdigest()

# =============================================================
# 3. Classe principal: KnowledgeMiner
# =============================================================

class KnowledgeMiner:
    """Minera conhecimento de múltiplas fontes e armazena no banco."""

    def __init__(self, db_path: str = KNOWLEDGE_DB, bypass=None):
        self.db_path = db_path
        self.bypass = bypass
        self.sources = {}
        self._embedding_model = None
        self._lock = threading.Lock()
        self._init_db()
        self._register_default_sources()

    def _init_db(self):
        """Garante que as tabelas necessárias existam."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Tabela de conhecimento (se não existir)
        c.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT UNIQUE,
                source TEXT,
                title TEXT,
                content TEXT,
                url TEXT,
                author TEXT,
                published_date TEXT,
                tags TEXT,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Tabela de fontes e metadados
        c.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_sources (
                source TEXT PRIMARY KEY,
                last_fetch TIMESTAMP,
                fetch_interval INTEGER DEFAULT 86400,
                enabled INTEGER DEFAULT 1,
                config TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def _register_default_sources(self):
        """Registra fontes padrão (podem ser habilitadas/desabilitadas)."""
        # Fontes RSS
        for feed in DEFAULT_NEWS_FEEDS:
            self.register_source("rss", feed, {"url": feed})

        # Wikipedia
        for category in DEFAULT_WIKI_CATEGORIES:
            self.register_source("wikipedia", f"wiki_{category}", {"category": category})

        # arXiv (se disponível)
        if HAS_ARXIV:
            self.register_source("arxiv", "arxiv_ai", {"query": "cat:cs.AI", "max_results": 10})

        # Stack Overflow (via API)
        self.register_source("stackoverflow", "stackoverflow_python", {"tagged": "python", "pagesize": 10})

        # GitHub Trending (via scraping ou API)
        self.register_source("github", "github_trending", {"language": "python"})

        # Hacker News
        self.register_source("hackernews", "hackernews_top", {"limit": 10})

        # Google News (rss)
        self.register_source("rss", "google_news_tech", {"url": "https://news.google.com/rss?topic=t&hl=en-US&gl=US&ceid=US:en"})

        # Reddit (via API pública)
        self.register_source("reddit", "reddit_python", {"subreddit": "python", "limit": 10})

        # Medium (via rss)
        self.register_source("rss", "medium_ai", {"url": "https://medium.com/feed/tag/artificial-intelligence"})

    def register_source(self, source_type: str, source_id: str, config: Dict):
        """Registra ou atualiza uma fonte de conhecimento."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO knowledge_sources (source, config, enabled)
            VALUES (?, ?, 1)
        ''', (source_id, json.dumps({"type": source_type, **config})))
        conn.commit()
        conn.close()
        self.sources[source_id] = {"type": source_type, "config": config}
        logger.info(f"[KnowledgeMiner] Fonte registrada: {source_id} (tipo={source_type})")

    def enable_source(self, source_id: str, enabled: bool = True):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('UPDATE knowledge_sources SET enabled = ? WHERE source = ?', (1 if enabled else 0, source_id))
        conn.commit()
        conn.close()

    def fetch_all(self, force: bool = False) -> Dict[str, int]:
        """Executa coleta de todas as fontes ativas."""
        results = {}
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT source, config, last_fetch, fetch_interval FROM knowledge_sources WHERE enabled = 1')
        rows = c.fetchall()
        conn.close()

        for source, config_json, last_fetch_str, interval in rows:
            if not force and last_fetch_str:
                last_fetch = datetime.fromisoformat(last_fetch_str)
                if datetime.now() - last_fetch < timedelta(seconds=interval):
                    logger.debug(f"[KnowledgeMiner] Fonte {source} pulada (intervalo não atingido)")
                    continue
            config = json.loads(config_json)
            source_type = config.get("type")
            try:
                count = self._fetch_from_source(source, source_type, config)
                results[source] = count
                # Atualiza timestamp
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute('UPDATE knowledge_sources SET last_fetch = ? WHERE source = ?', (datetime.now().isoformat(), source))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"[KnowledgeMiner] Falha na fonte {source}: {e}")
                results[source] = -1
        return results

    def _fetch_from_source(self, source_id: str, source_type: str, config: Dict) -> int:
        """Dispara a coleta específica por tipo de fonte."""
        if source_type == "rss":
            return self._fetch_rss(source_id, config)
        elif source_type == "wikipedia":
            return self._fetch_wikipedia_category(source_id, config)
        elif source_type == "arxiv":
            return self._fetch_arxiv(source_id, config)
        elif source_type == "stackoverflow":
            return self._fetch_stackoverflow(source_id, config)
        elif source_type == "github":
            return self._fetch_github_trending(source_id, config)
        elif source_type == "hackernews":
            return self._fetch_hackernews(source_id, config)
        elif source_type == "reddit":
            return self._fetch_reddit(source_id, config)
        else:
            logger.warning(f"[KnowledgeMiner] Tipo de fonte desconhecido: {source_type}")
            return 0

    # ---------------------------------------------------------
    # 3.1 RSS Feeds
    # ---------------------------------------------------------
    def _fetch_rss(self, source_id: str, config: Dict) -> int:
        if not HAS_FEEDPARSER:
            logger.warning("feedparser não instalado")
            return 0
        url = config.get("url")
        if not url:
            return 0
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries[:config.get("limit", 20)]:
            title = entry.get("title", "")
            content = entry.get("summary", entry.get("description", ""))
            link = entry.get("link")
            published = entry.get("published")
            item = KnowledgeItem(
                source=source_id,
                title=title,
                content=content,
                url=link,
                published_date=published,
                tags=["rss", "news"]
            )
            if self._save_if_new(item):
                count += 1
        return count

    # ---------------------------------------------------------
    # 3.2 Wikipedia
    # ---------------------------------------------------------
    def _fetch_wikipedia_category(self, source_id: str, config: Dict) -> int:
        if not HAS_WIKIPEDIA:
            logger.warning("wikipedia não instalado")
            return 0
        category = config.get("category")
        if not category:
            return 0
        # Busca páginas de uma categoria (limitado)
        try:
            # Usa a API de categorias
            import wikipedia
            # Tenta obter a página de categoria (não é direto)
            # Método alternativo: busca páginas relacionadas ao tópico
            search_results = wikipedia.search(category, results=config.get("max_results", 10))
            count = 0
            for title in search_results:
                try:
                    page = wikipedia.page(title)
                    item = KnowledgeItem(
                        source=source_id,
                        title=page.title,
                        content=page.summary,
                        url=page.url,
                        tags=["wikipedia", category]
                    )
                    if self._save_if_new(item):
                        count += 1
                except Exception:
                    continue
            return count
        except Exception as e:
            logger.error(f"Erro na wikipedia: {e}")
            return 0

    # ---------------------------------------------------------
    # 3.3 arXiv
    # ---------------------------------------------------------
    def _fetch_arxiv(self, source_id: str, config: Dict) -> int:
        if not HAS_ARXIV:
            logger.warning("arxiv não instalado")
            return 0
        query = config.get("query", "cat:cs.AI")
        max_results = config.get("max_results", 10)
        search = arxiv.Search(query=query, max_results=max_results, sort_by=arxiv.SortCriterion.SubmittedDate)
        count = 0
        for result in search.results():
            item = KnowledgeItem(
                source=source_id,
                title=result.title,
                content=result.summary,
                url=result.entry_id,
                author=", ".join([a.name for a in result.authors]),
                published_date=result.published.isoformat(),
                tags=["arxiv", "paper"]
            )
            if self._save_if_new(item):
                count += 1
        return count

    # ---------------------------------------------------------
    # 3.4 Stack Overflow
    # ---------------------------------------------------------
    def _fetch_stackoverflow(self, source_id: str, config: Dict) -> int:
        # Usa a API pública (sem chave, limitada)
        base = "https://api.stackexchange.com/2.3/questions"
        params = {
            "order": "desc",
            "sort": "activity",
            "tagged": config.get("tagged", "python"),
            "site": "stackoverflow",
            "pagesize": config.get("pagesize", 10)
        }
        try:
            resp = requests.get(base, params=params, timeout=10)
            data = resp.json()
            count = 0
            for item in data.get("items", []):
                title = item.get("title")
                content = item.get("body", "")
                # Limpar HTML (opcional)
                if HAS_BEAUTIFULSOUP:
                    soup = BeautifulSoup(content, "html.parser")
                    content = soup.get_text()
                url = item.get("link")
                tags = item.get("tags", [])
                item_obj = KnowledgeItem(
                    source=source_id,
                    title=title,
                    content=content,
                    url=url,
                    tags=tags,
                    published_date=datetime.fromtimestamp(item.get("creation_date")).isoformat()
                )
                if self._save_if_new(item_obj):
                    count += 1
            return count
        except Exception as e:
            logger.error(f"Stack Overflow falhou: {e}")
            return 0

    # ---------------------------------------------------------
    # 3.5 GitHub Trending (via scraping)
    # ---------------------------------------------------------
    def _fetch_github_trending(self, source_id: str, config: Dict) -> int:
        language = config.get("language", "python")
        url = f"https://github.com/trending/{language}"
        if not HAS_BEAUTIFULSOUP:
            logger.warning("BeautifulSoup não instalado para GitHub trending")
            return 0
        try:
            resp = requests.get(url, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            repos = soup.select("article.Box-row")
            count = 0
            for repo in repos[:config.get("limit", 10)]:
                title_elem = repo.select_one("h2 a")
                if not title_elem:
                    continue
                full_name = title_elem.get_text(strip=True)
                description_elem = repo.select_one("p")
                description = description_elem.get_text(strip=True) if description_elem else ""
                url = "https://github.com" + title_elem.get("href")
                stars_elem = repo.select_one("a[href*='stargazers']")
                stars = stars_elem.get_text(strip=True) if stars_elem else "0"
                item = KnowledgeItem(
                    source=source_id,
                    title=full_name,
                    content=f"{description}\nStars: {stars}",
                    url=url,
                    tags=["github", language, "trending"]
                )
                if self._save_if_new(item):
                    count += 1
            return count
        except Exception as e:
            logger.error(f"GitHub trending falhou: {e}")
            return 0

    # ---------------------------------------------------------
    # 3.6 Hacker News
    # ---------------------------------------------------------
    def _fetch_hackernews(self, source_id: str, config: Dict) -> int:
        # Obtém os top stories
        try:
            resp = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10)
            top_ids = resp.json()[:config.get("limit", 10)]
            count = 0
            for item_id in top_ids:
                story_url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
                story_resp = requests.get(story_url, timeout=5)
                story = story_resp.json()
                if story and "title" in story:
                    item = KnowledgeItem(
                        source=source_id,
                        title=story.get("title", ""),
                        content=story.get("text", ""),
                        url=story.get("url"),
                        tags=["hackernews"]
                    )
                    if self._save_if_new(item):
                        count += 1
            return count
        except Exception as e:
            logger.error(f"HackerNews falhou: {e}")
            return 0

    # ---------------------------------------------------------
    # 3.7 Reddit
    # ---------------------------------------------------------
    def _fetch_reddit(self, source_id: str, config: Dict) -> int:
        subreddit = config.get("subreddit", "python")
        url = f"https://www.reddit.com/r/{subreddit}/top.json?limit={config.get('limit', 10)}"
        headers = {"User-Agent": "AtenaKnowledgeMiner/1.0"}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()
            posts = data.get("data", {}).get("children", [])
            count = 0
            for post in posts:
                post_data = post.get("data", {})
                title = post_data.get("title")
                selftext = post_data.get("selftext", "")
                url = post_data.get("url")
                permalink = "https://reddit.com" + post_data.get("permalink")
                item = KnowledgeItem(
                    source=source_id,
                    title=title,
                    content=selftext,
                    url=permalink,
                    tags=["reddit", subreddit]
                )
                if self._save_if_new(item):
                    count += 1
            return count
        except Exception as e:
            logger.error(f"Reddit falhou: {e}")
            return 0

    # ---------------------------------------------------------
    # 4. Armazenamento e deduplicação
    # ---------------------------------------------------------
    def _save_if_new(self, item: KnowledgeItem) -> bool:
        """Salva item se ainda não existir (baseado no hash)."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Verifica se hash já existe
        c.execute('SELECT 1 FROM knowledge_items WHERE hash = ?', (item.hash,))
        if c.fetchone():
            conn.close()
            return False
        # Insere novo
        c.execute('''
            INSERT INTO knowledge_items (hash, source, title, content, url, author, published_date, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item.hash,
            item.source,
            item.title[:500],
            item.content[:5000],
            item.url,
            item.author,
            item.published_date,
            json.dumps(item.tags)
        ))
        conn.commit()
        conn.close()
        return True

    # ---------------------------------------------------------
    # 5. Busca e recuperação
    # ---------------------------------------------------------
    def search_knowledge(self, query: str, limit: int = 10) -> List[Dict]:
        """Busca conhecimento por similaridade de texto (usando SQL LIKE ou TF-IDF)."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Busca simples por palavras-chave (pode ser expandido)
        words = query.lower().split()
        conditions = []
        for word in words:
            conditions.append("(title LIKE ? OR content LIKE ?)")
        if not conditions:
            return []
        sql = "SELECT title, content, url, source, tags FROM knowledge_items WHERE " + " OR ".join(conditions)
        params = [f"%{w}%" for w in words for _ in range(2)]
        c.execute(sql, params)
        rows = c.fetchmany(limit)
        conn.close()
        return [{"title": r[0], "content": r[1], "url": r[2], "source": r[3], "tags": json.loads(r[4])} for r in rows]

    def get_random_knowledge(self, limit: int = 5) -> List[Dict]:
        """Retorna itens aleatórios para enriquecer o contexto."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT title, content, url, source, tags FROM knowledge_items ORDER BY RANDOM() LIMIT ?', (limit,))
        rows = c.fetchall()
        conn.close()
        return [{"title": r[0], "content": r[1], "url": r[2], "source": r[3], "tags": json.loads(r[4])} for r in rows]

    # ---------------------------------------------------------
    # 6. Geração de embeddings (opcional)
    # ---------------------------------------------------------
    def _get_embedding_model(self):
        if self._embedding_model is None and HAS_SENTENCE_TRANSFORMERS:
            try:
                self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            except:
                pass
        return self._embedding_model

    def embed_knowledge(self, item_id: int, text: str) -> Optional[List[float]]:
        model = self._get_embedding_model()
        if model:
            return model.encode(text).tolist()
        return None

    # ---------------------------------------------------------
    # 7. Integração com o módulo de bypass
    # ---------------------------------------------------------
    def run_periodic_mining(self, interval_seconds: int = 3600):
        """Executa a mineração em loop (thread separada)."""
        def _loop():
            while True:
                try:
                    self.fetch_all()
                except Exception as e:
                    logger.error(f"Mineração periódica falhou: {e}")
                time.sleep(interval_seconds)
        threading.Thread(target=_loop, daemon=True).start()
