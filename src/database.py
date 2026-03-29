import sqlite3
import json
import os
from typing import List, Dict, Optional
from .provider import ProviderState, ModelState

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS providers (
                    name TEXT PRIMARY KEY COLLATE NOCASE,
                    type TEXT,
                    api_key TEXT,
                    url TEXT,
                    api_url TEXT,
                    free BOOLEAN,
                    status TEXT,
                    token_price_1k REAL DEFAULT 0.0,
                    max_quota_min INTEGER DEFAULT 0,
                    max_quota_day INTEGER DEFAULT 0,
                    current_quota_min INTEGER DEFAULT 0,
                    current_quota_day INTEGER DEFAULT 0,
                    last_reset_min REAL,
                    last_reset_day REAL,
                    retry_count INTEGER DEFAULT 0,
                    avg_error_rate REAL DEFAULT 0.0,
                    p99_latency REAL DEFAULT 0.0,
                    cool_down_until REAL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY COLLATE NOCASE,
                    provider_name TEXT COLLATE NOCASE,
                    model_id TEXT,
                    tags TEXT,
                    free BOOLEAN,
                    price_input_1k REAL DEFAULT 0.0,
                    price_output_1k REAL DEFAULT 0.0,
                    last_used_at REAL,
                    success_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    FOREIGN KEY (provider_name) REFERENCES providers (name)
                )
            """)
            conn.commit()

    def save_provider(self, p: ProviderState):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO providers (
                    name, type, api_key, url, api_url, free, status, token_price_1k,
                    max_quota_min, max_quota_day, current_quota_min, current_quota_day,
                    last_reset_min, last_reset_day, retry_count, avg_error_rate, p99_latency,
                    cool_down_until
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p.name, p.type, p.api_key, p.url, p.api_url, p.free, p.status, p.token_price_1k,
                p.max_quota_min, p.max_quota_day, p.current_quota_min, p.current_quota_day,
                p.last_reset_min, p.last_reset_day, p.retry_count, p.average_error_rate, p.p99_latency_ms,
                p.cool_down_until
            ))
            conn.commit()
            
            # Save models
            for m in p.models.values():
                cursor.execute("""
                    INSERT OR REPLACE INTO models (
                        id, provider_name, model_id, tags, free,
                        price_input_1k, price_output_1k, last_used_at, success_count, error_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"{p.name}:{m.id}", p.name, m.id, json.dumps(m.tags), m.free,
                    m.price_input_1k, m.price_output_1k, m.last_used_at, m.success_count, m.error_count
                ))
            conn.commit()

    def load_all_providers(self) -> List[ProviderState]:
        providers = []
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM providers")
            rows = cursor.fetchall()
            
            for row in rows:
                p = ProviderState(
                    name=row['name'],
                    type=row['type'],
                    free=bool(row['free']),
                    api_key=row['api_key'],
                    url=row['url'] if 'url' in row.keys() else "",
                    api_url=row['api_url'] if 'api_url' in row.keys() else "",
                    token_price_1k=row['token_price_1k'],
                    max_quota_min=row['max_quota_min'],
                    max_quota_day=row['max_quota_day'],
                    current_quota_min=row['current_quota_min'],
                    current_quota_day=row['current_quota_day'],
                    last_reset_min=row['last_reset_min'],
                    last_reset_day=row['last_reset_day'],
                    status=row['status'],
                    retry_count=row['retry_count'],
                    cool_down_until=row['cool_down_until'] if 'cool_down_until' in row.keys() else None
                )
                
                # Load models for this provider
                cursor.execute("SELECT * FROM models WHERE provider_name = ?", (p.name,))
                m_rows = cursor.fetchall()
                for m_row in m_rows:
                    m = ModelState(
                        id=m_row['model_id'] or m_row['id'],
                        tags=json.loads(m_row['tags']),
                        free=bool(m_row['free']),
                        price_input_1k=m_row['price_input_1k'],
                        price_output_1k=m_row['price_output_1k'],
                        success_count=m_row['success_count'],
                        error_count=m_row['error_count'],
                        last_used_at=m_row['last_used_at']
                    )
                    p.models[m.id] = m
                providers.append(p)
        return providers

    def delete_provider(self, name: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM models WHERE provider_name = ?", (name,))
            cursor.execute("DELETE FROM providers WHERE name = ?", (name,))
            conn.commit()
