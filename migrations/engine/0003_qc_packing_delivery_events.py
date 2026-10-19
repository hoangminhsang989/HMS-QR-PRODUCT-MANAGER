"""Stage 4 event-based QC, packing and delivery workflows (engine format)."""

TRACKING_WORKFLOW_EVENTS = """
CREATE TABLE tracking_workflow_events (
    internal_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    tracking_item_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    quantity NUMERIC(18,4),
    notes TEXT,
    machining_type_id TEXT,
    process_report_id TEXT,
    actor_user_id TEXT NOT NULL,
    actor_display_name_snapshot TEXT NOT NULL,
    server_timestamp DATETIME NOT NULL,
    client_timestamp DATETIME,
    device_id TEXT,
    sequence_number INTEGER NOT NULL,
    revision INTEGER NOT NULL,
    supersedes_event_id TEXT,
    status TEXT NOT NULL,
    FOREIGN KEY (tracking_item_id) REFERENCES order_tracking_items(internal_id),
    FOREIGN KEY (machining_type_id) REFERENCES machining_types(internal_id),
    FOREIGN KEY (process_report_id) REFERENCES process_report_events(internal_id),
    FOREIGN KEY (actor_user_id) REFERENCES operators(internal_id),
    FOREIGN KEY (supersedes_event_id) REFERENCES tracking_workflow_events(internal_id),
    UNIQUE (request_id),
    UNIQUE (tracking_item_id, sequence_number, revision)
)
"""


def upgrade(transaction):
    """Create only the workflow-event schema owned by Stage 4."""

    transaction.execute(TRACKING_WORKFLOW_EVENTS)
