-- MySQL 5.7+: run once as a DBA in the chosen database before starting the service.
-- No USE statement or credentials: select the database through your SQL client.
-- IF NOT EXISTS does not migrate incompatible existing tables.
CREATE TABLE IF NOT EXISTS sorting_events (
    event_id VARCHAR(64) NOT NULL,
    site_id VARCHAR(64) NOT NULL,
    camera_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(40) NOT NULL,
    status VARCHAR(24) NOT NULL,
    start_at VARCHAR(40) NOT NULL,
    end_at VARCHAR(40),
    duration_seconds FLOAT,
    review_status VARCHAR(24),
    snapshot_path VARCHAR(1024),
    clip_path VARCHAR(1024),
    payload JSON NOT NULL,
    PRIMARY KEY (event_id),
    INDEX ix_sorting_events_camera_id (camera_id),
    INDEX ix_sorting_events_event_type (event_type),
    INDEX ix_sorting_events_start_at (start_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sorting_camera_status (
    camera_id VARCHAR(64) NOT NULL,
    site_id VARCHAR(64) NOT NULL,
    state VARCHAR(32) NOT NULL,
    heartbeat_at VARCHAR(40) NOT NULL,
    payload JSON NOT NULL,
    PRIMARY KEY (camera_id, site_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
