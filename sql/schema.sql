-- Schema for the Urban Pulse database (PostgreSQL)
-- Run by src/load.py, or paste into DBeaver while connected to urban_pulse_db.

CREATE TABLE IF NOT EXISTS service_requests (
    unique_key                      BIGINT PRIMARY KEY,
    created_date                    TIMESTAMP NOT NULL,
    closed_date                     TIMESTAMP,
    due_date                        TIMESTAMP,
    agency                          TEXT,
    agency_name                     TEXT,
    complaint_type                  TEXT,
    descriptor                      TEXT,
    location_type                   TEXT,
    address_type                    TEXT,
    incident_zip                    TEXT,
    incident_address                TEXT,
    city                            TEXT,
    borough                         TEXT,
    status                          TEXT,
    resolution_description          TEXT,
    resolution_action_updated_date  TIMESTAMP,
    community_board                 TEXT,
    council_district                INTEGER,
    police_precinct                 TEXT,
    open_data_channel_type          TEXT,
    x_coordinate_state_plane        DOUBLE PRECISION,
    y_coordinate_state_plane        DOUBLE PRECISION,
    latitude                        DOUBLE PRECISION,
    longitude                       DOUBLE PRECISION,

    -- quality flags
    flag_closed_before_created          BOOLEAN,
    flag_future_date                    BOOLEAN,
    flag_status_closed_no_closed_date   BOOLEAN,
    flag_closed_date_status_not_closed  BOOLEAN,
    flag_invalid_zip                    BOOLEAN,
    flag_missing_coordinates            BOOLEAN,
    flag_coordinates_outside_nyc        BOOLEAN,

    -- derived fields
    is_closed            SMALLINT,
    resolution_hours     DOUBLE PRECISION,
    is_over_72h          SMALLINT,
    created_year         SMALLINT,
    created_month        SMALLINT,
    created_year_month   TEXT,
    created_weekday      TEXT,
    created_weekday_num  SMALLINT,
    created_hour         SMALLINT
);

CREATE INDEX IF NOT EXISTS idx_sr_created_date   ON service_requests (created_date);
CREATE INDEX IF NOT EXISTS idx_sr_agency         ON service_requests (agency);
CREATE INDEX IF NOT EXISTS idx_sr_complaint_type ON service_requests (complaint_type);
CREATE INDEX IF NOT EXISTS idx_sr_borough        ON service_requests (borough);
CREATE INDEX IF NOT EXISTS idx_sr_year_month     ON service_requests (created_year_month);
