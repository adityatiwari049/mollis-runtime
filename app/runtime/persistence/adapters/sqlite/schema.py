import sqlite3

CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    retry_count INTEGER DEFAULT 0,
    metadata TEXT,
    error_message TEXT,
    version INTEGER NOT NULL
);
"""

CREATE_WORKERS_TABLE = """
CREATE TABLE IF NOT EXISTS workers (
    worker_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    current_task_id TEXT,
    heartbeat_time TEXT NOT NULL,
    tasks_processed INTEGER DEFAULT 0,
    failures INTEGER DEFAULT 0,
    start_time TEXT NOT NULL,
    version INTEGER NOT NULL
);
"""

CREATE_QUEUE_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS queue_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    queued_task_ids TEXT NOT NULL,
    size INTEGER NOT NULL,
    capacity INTEGER,
    policy_type TEXT NOT NULL,
    version INTEGER NOT NULL
);
"""

CREATE_SCHEDULER_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS scheduler_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    started INTEGER NOT NULL,
    uptime_seconds REAL NOT NULL,
    delayed_task_ids TEXT NOT NULL,
    active_timeouts TEXT NOT NULL,
    timestamp TEXT,
    version INTEGER NOT NULL
);
"""

CREATE_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    state_data TEXT NOT NULL,
    schema_version INTEGER NOT NULL
);
"""

CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    sequence_number INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    runtime_id TEXT NOT NULL,
    correlation_id TEXT,
    causation_id TEXT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    version INTEGER NOT NULL,
    metadata TEXT,
    data_payload TEXT NOT NULL
);
"""

CREATE_WORKFLOW_DEFINITIONS_TABLE = """
CREATE TABLE IF NOT EXISTS workflow_definitions (
    name TEXT PRIMARY KEY,
    definition_json TEXT NOT NULL,
    version TEXT NOT NULL
);
"""

CREATE_WORKFLOW_INSTANCES_TABLE = """
CREATE TABLE IF NOT EXISTS workflow_instances (
    instance_id TEXT PRIMARY KEY,
    workflow_name TEXT NOT NULL,
    status TEXT NOT NULL,
    instance_json TEXT NOT NULL,
    version TEXT NOT NULL
);
"""

def initialize_schema(conn: sqlite3.Connection) -> None:
    """
    Apply database schema definitions to the SQLite connection.
    Enables WAL mode and foreign key constraints.
    """
    # SQLite optimizations
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    
    # Create tables
    with conn:
        conn.execute(CREATE_TASKS_TABLE)
        conn.execute(CREATE_WORKERS_TABLE)
        conn.execute(CREATE_QUEUE_STATE_TABLE)
        conn.execute(CREATE_SCHEDULER_STATE_TABLE)
        conn.execute(CREATE_SNAPSHOTS_TABLE)
        conn.execute(CREATE_EVENTS_TABLE)
        conn.execute(CREATE_WORKFLOW_DEFINITIONS_TABLE)
        conn.execute(CREATE_WORKFLOW_INSTANCES_TABLE)
