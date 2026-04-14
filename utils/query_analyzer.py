"""
Утилита для анализа медленных запросов PostgreSQL
Логирует медленные запросы и выполняет EXPLAIN ANALYZE
"""
import logging
import json
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Директория для сохранения планов запросов
PROJECT_ROOT = Path(__file__).parent.parent
QUERY_PLANS_DIR = PROJECT_ROOT / "logs" / "query_plans"
QUERY_PLANS_DIR.mkdir(parents=True, exist_ok=True)

# Порог для медленных запросов (в секундах)
SLOW_QUERY_THRESHOLD = 1.0


class QueryAnalyzer:
    """Анализатор запросов PostgreSQL"""
    
    def __init__(self, slow_query_threshold: float = SLOW_QUERY_THRESHOLD):
        self.slow_query_threshold = slow_query_threshold
        self.plans_dir = QUERY_PLANS_DIR
    
    def log_slow_query(
        self,
        query: str,
        execution_time: float,
        params: Optional[Dict[str, Any]] = None
    ):
        """
        Логировать медленный запрос
        
        Args:
            query: SQL запрос
            execution_time: время выполнения в секундах
            params: параметры запроса
        """
        if execution_time >= self.slow_query_threshold:
            logger.warning(
                f"🐌 Медленный запрос ({execution_time:.3f}s):\n"
                f"Query: {query[:200]}...\n"
                f"Params: {params}"
            )
    
    def explain_analyze(
        self,
        db: Session,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        save_plan: bool = True
    ) -> Dict[str, Any]:
        """
        Выполнить EXPLAIN ANALYZE для запроса
        
        Args:
            db: сессия БД
            query: SQL запрос
            params: параметры запроса
            save_plan: сохранить план в файл
            
        Returns:
            Словарь с результатами EXPLAIN ANALYZE
        """
        try:
            # Добавляем EXPLAIN ANALYZE к запросу
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON) {query}"
            
            result = db.execute(text(explain_query), params or {})
            plan_data = result.fetchone()[0]  # EXPLAIN возвращает JSON
            
            if save_plan:
                self._save_plan(query, plan_data, params)
            
            return {
                "success": True,
                "plan": plan_data,
                "query": query,
                "params": params
            }
        
        except Exception as e:
            logger.error(f"Ошибка при выполнении EXPLAIN ANALYZE: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def _save_plan(self, query: str, plan_data: Dict, params: Optional[Dict] = None):
        """Сохранить план выполнения в файл"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        
        filename = f"plan_{timestamp}_{query_hash}.json"
        filepath = self.plans_dir / filename
        
        plan_info = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "params": params,
            "plan": plan_data
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(plan_info, f, indent=2, ensure_ascii=False)
            logger.info(f"План запроса сохранен: {filepath}")
        except Exception as e:
            logger.error(f"Ошибка сохранения плана: {e}")


# Глобальный экземпляр анализатора
query_analyzer = QueryAnalyzer()
