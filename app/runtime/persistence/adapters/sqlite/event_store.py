import json
import sqlite3
import threading
from typing import Optional, List, Dict, Any

from runtime.persistence.domain.ports import EventStore
from runtime.persistence.domain.events import RuntimeEvent

class SQLiteEventStore(EventStore):
    """
    SQLite concrete implementation of the EventStore port.
    Guarantees strict ordering of appends via auto-increment sequence numbers.
    """
    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock):
        """
        Initialize the SQLiteEventStore.

        Args:
            conn (sqlite3.Connection): Active SQLite connection.
            lock (threading.Lock): Shared thread-safety lock.
        """
        self._conn = conn
        self._lock = lock

    def append(self, event: RuntimeEvent) -> None:
        query = """
        INSERT INTO events (
            event_id, runtime_id, correlation_id, causation_id, timestamp, event_type, version, metadata, data_payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        payload = event.to_dict()
        with self._lock:
            with self._conn:
                self._conn.execute(
                    query,
                    (
                        event.event_id,
                        event.runtime_id,
                        event.correlation_id,
                        event.causation_id,
                        event.timestamp,
                        payload["event_type"],
                        event.version,
                        json.dumps(event.metadata),
                        json.dumps(payload)
                    )
                )

    def append_batch(self, events: List[RuntimeEvent]) -> None:
        query = """
        INSERT INTO events (
            event_id, runtime_id, correlation_id, causation_id, timestamp, event_type, version, metadata, data_payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self._lock:
            with self._conn:
                for event in events:
                    payload = event.to_dict()
                    self._conn.execute(
                        query,
                        (
                            event.event_id,
                            event.runtime_id,
                            event.correlation_id,
                            event.causation_id,
                            event.timestamp,
                            payload["event_type"],
                            event.version,
                            json.dumps(event.metadata),
                            json.dumps(payload)
                        )
                    )

    def load(self, event_id: str) -> Optional[RuntimeEvent]:
        query = "SELECT data_payload FROM events WHERE event_id = ?;"
        with self._lock:
            cursor = self._conn.execute(query, (event_id,))
            row = cursor.fetchone()
        if not row:
            return None
        payload = json.loads(row[0])
        return RuntimeEvent.from_dict(payload)

    def stream(self, limit: int = 100, offset: int = 0) -> List[RuntimeEvent]:
        query = "SELECT data_payload FROM events ORDER BY sequence_number ASC LIMIT ? OFFSET ?;"
        with self._lock:
            cursor = self._conn.execute(query, (limit, offset))
            rows = cursor.fetchall()
        
        results = []
        for row in rows:
            payload = json.loads(row[0])
            results.append(RuntimeEvent.from_dict(payload))
        return results

    def stream_from(self, start_timestamp: str, limit: int = 100, offset: int = 0) -> List[RuntimeEvent]:
        query = """
        SELECT data_payload FROM events 
        WHERE timestamp >= ? 
        ORDER BY sequence_number ASC LIMIT ? OFFSET ?;
        """
        with self._lock:
            cursor = self._conn.execute(query, (start_timestamp, limit, offset))
            rows = cursor.fetchall()
        
        results = []
        for row in rows:
            payload = json.loads(row[0])
            results.append(RuntimeEvent.from_dict(payload))
        return results

    def replay(self, runtime_id: str) -> List[RuntimeEvent]:
        query = "SELECT data_payload FROM events WHERE runtime_id = ? ORDER BY sequence_number ASC;"
        with self._lock:
            cursor = self._conn.execute(query, (runtime_id,))
            rows = cursor.fetchall()
        
        results = []
        for row in rows:
            payload = json.loads(row[0])
            results.append(RuntimeEvent.from_dict(payload))
        return results

    def count(self) -> int:
        query = "SELECT COUNT(*) FROM events;"
        with self._lock:
            cursor = self._conn.execute(query)
            row = cursor.fetchone()
        return row[0] if row else 0

    def truncate(self) -> None:
        query = "DELETE FROM events;"
        with self._lock:
            with self._conn:
                self._conn.execute(query)
