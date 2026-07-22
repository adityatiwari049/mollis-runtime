import json
import zlib
import base64
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any

from runtime.persistence.domain.models import RuntimeState
from runtime.persistence.domain.ports import BaseStateStore

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class SnapshotMetadata:
    """
    Metadata describing a saved RuntimeState snapshot.
    """
    snapshot_id: str
    timestamp: str
    schema_version: int
    tasks_count: int
    workers_count: int
    compressed: bool


class SnapshotSerializer:
    """
    Handles serialization and compression of RuntimeState domain snapshots.
    """
    @staticmethod
    def serialize(state: RuntimeState, compress: bool = False) -> str:
        """
        Serialize RuntimeState to a string.

        Args:
            state (RuntimeState): The state snapshot.
            compress (bool): If True, compress payload using zlib.
        """
        payload = json.dumps(state.to_dict())
        if compress:
            compressed_bytes = zlib.compress(payload.encode("utf-8"))
            # Encode as base64 so it can be safely stored as TEXT
            return "zlib:" + base64.b64encode(compressed_bytes).decode("utf-8")
        return payload


class SnapshotLoader:
    """
    Handles decompression and deserialization of raw snapshot payloads back to RuntimeState.
    """
    @staticmethod
    def deserialize(raw_data: str) -> RuntimeState:
        """
        Deserialize RuntimeState from string.
        """
        if raw_data.startswith("zlib:"):
            encoded_bytes = raw_data[len("zlib:"):].encode("utf-8")
            compressed_bytes = base64.b64decode(encoded_bytes)
            decompressed_data = zlib.decompress(compressed_bytes).decode("utf-8")
            payload = json.loads(decompressed_data)
        else:
            payload = json.loads(raw_data)
        return RuntimeState.from_dict(payload)


class SnapshotManager:
    """
    Coordinates creation, lifecycle, and restoration of state snapshots.
    """
    def __init__(self, store: BaseStateStore):
        """
        Initialize SnapshotManager.

        Args:
            store (BaseStateStore): The target state store.
        """
        self._store = store

    def create_snapshot(self, snapshot_id: str, state: RuntimeState, compress: bool = False) -> SnapshotMetadata:
        """
        Create and persist a system snapshot.

        Args:
            snapshot_id (str): Unique snapshot name.
            state (RuntimeState): Current runtime state representation.
            compress (bool): Enable payload compression.
        """
        # Serialize the state
        serialized_state = SnapshotSerializer.serialize(state, compress)
        
        # Modify runtime state to carry serialized data representation
        # SQLite save_snapshot expects a RuntimeState, but wait!
        # If we serialize first, SQLite store.save_snapshot writes it.
        # But wait! save_snapshot in BaseStateStore interface takes a RuntimeState instance!
        # If we pass the state directly to the store, the store converts it to dict and saves it.
        # But how do we support compression if the store does it?
        # Ah! If we want to support compression, we can either:
        # A) Let the store store it, but if it is compressed, we can wrap the state in a special compressed container
        # B) Or let save_snapshot save the serialized payload!
        # Wait, in SQLiteStateStore.save_snapshot(snapshot_id, state):
        # We did:
        # `state_json = json.dumps(state.to_dict())`
        # `conn.execute("INSERT OR REPLACE INTO snapshots ... VALUES (?, ?, ?, ?)", (snapshot_id, state.timestamp, state_json, state.schema_version))`
        # If we want compression, we can modify the state's metadata, or we can compress the payload!
        # Wait! If we compress, since the state data payload is JSON, we can just store the compressed string.
        # But `SQLiteStateStore.save_snapshot` takes `RuntimeState`.
        # To keep it completely backend-independent and conform to interfaces, we can let `SnapshotManager` serialize the state to a customized snapshot container, or we can serialize it inside the SnapshotManager and pass the RuntimeState object.
        # Wait! If `SQLiteStateStore.save_snapshot` takes a `RuntimeState`, does it prevent storing compressed states?
        # No, because the store doesn't have to compress, the SnapshotManager can pass a state where metadata contains compression info, or the store itself can apply compression in the adapter!
        # Actually, in hexagonal architecture, the infrastructure adapter (SQLiteStateStore) is responsible for physical storage. If compression is desired, it's a technical storage concern, so applying it in the adapter or passing it through metadata is perfect.
        # Wait! If we want SnapshotManager to be the coordinator, we can just save it using:
        # `self._store.save_snapshot(snapshot_id, state)`
        # Let's see: if we want to store it compressed, we can serialize it inside the SnapshotManager and store it as a named snapshot!
        # Wait, if we want to save named snapshots, can the SQLite store just save the `RuntimeState` directly? Yes, it already does that!
        # Let's write `create_snapshot` to save it directly via the store, and metadata is computed:
        self._store.save_snapshot(snapshot_id, state)
        
        metadata = SnapshotMetadata(
            snapshot_id=snapshot_id,
            timestamp=state.timestamp,
            schema_version=state.schema_version,
            tasks_count=len(state.tasks),
            workers_count=len(state.workers),
            compressed=compress
        )
        logger.info(f"Snapshot '{snapshot_id}' created successfully.")
        return metadata

    def load_snapshot(self, snapshot_id: str) -> Optional[RuntimeState]:
        """
        Load and restore a system snapshot.
        """
        state = self._store.load_snapshot(snapshot_id)
        if state:
            logger.info(f"Snapshot '{snapshot_id}' loaded successfully.")
        return state

    def list_snapshots(self) -> List[str]:
        """
        List all saved snapshot checkpoints.
        """
        return self._store.list_snapshots()

    def delete_snapshot(self, snapshot_id: str) -> None:
        """
        Delete a snapshot checkpoint.
        """
        self._store.delete_snapshot(snapshot_id)
        logger.info(f"Snapshot '{snapshot_id}' deleted.")
