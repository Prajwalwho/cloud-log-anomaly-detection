-- =============================================================
-- Cloud Log Anomaly Detection — database initialization
-- Runs automatically on the first start of the Postgres container.
-- =============================================================

-- ---------- services ----------
CREATE TABLE services (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------- model_registry ----------
CREATE TABLE model_registry (
    id               SERIAL PRIMARY KEY,
    name             VARCHAR(100)     NOT NULL,
    version          VARCHAR(20)      NOT NULL,
    algorithm        VARCHAR(50)      NOT NULL,
    file_path        TEXT             NOT NULL,
    parameters       JSONB            NOT NULL DEFAULT '{}',
    threshold        DOUBLE PRECISION,
    training_data    TEXT,
    training_samples INTEGER,
    metrics          JSONB            NOT NULL DEFAULT '{}',
    is_active        BOOLEAN          NOT NULL DEFAULT FALSE,
    trained_at       TIMESTAMPTZ      NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);

-- Only one model can be active at a time
CREATE UNIQUE INDEX uq_model_registry_one_active
    ON model_registry (is_active) WHERE is_active;

-- ---------- detection_windows ----------
CREATE TABLE detection_windows (
    id               BIGSERIAL PRIMARY KEY,
    service_id       INTEGER          NOT NULL REFERENCES services(id),
    model_id         INTEGER          NOT NULL REFERENCES model_registry(id),
    window_start     TIMESTAMPTZ      NOT NULL,
    window_end       TIMESTAMPTZ      NOT NULL,
    log_count        INTEGER          NOT NULL DEFAULT 0,
    error_count      INTEGER          NOT NULL DEFAULT 0,
    warn_count       INTEGER          NOT NULL DEFAULT 0,
    avg_latency_ms   DOUBLE PRECISION,
    p95_latency_ms   DOUBLE PRECISION,
    unique_templates INTEGER          NOT NULL DEFAULT 0,
    new_templates    INTEGER          NOT NULL DEFAULT 0,
    anomaly_score    DOUBLE PRECISION NOT NULL CHECK (anomaly_score BETWEEN 0 AND 1),
    is_anomaly       BOOLEAN          NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ      NOT NULL DEFAULT now(),
    CHECK (window_end > window_start),
    UNIQUE (service_id, window_start, model_id)
);

CREATE INDEX idx_windows_service_time ON detection_windows (service_id, window_start DESC);
CREATE INDEX idx_windows_time         ON detection_windows (window_start);

-- ---------- alerts ----------
CREATE TABLE alerts (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id        INTEGER      NOT NULL REFERENCES services(id),
    severity          VARCHAR(10)  NOT NULL
                      CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    title             VARCHAR(200) NOT NULL,
    message           TEXT,
    status            VARCHAR(15)  NOT NULL DEFAULT 'OPEN'
                      CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')),
    occurrence_count  INTEGER      NOT NULL DEFAULT 1,
    first_seen_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_seen_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    acknowledged_at   TIMESTAMPTZ,
    acknowledged_by   VARCHAR(100),
    resolved_at       TIMESTAMPTZ,
    notification_sent BOOLEAN      NOT NULL DEFAULT FALSE,
    notified_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_alerts_status_time ON alerts (status, created_at DESC);

-- ---------- anomalies ----------
CREATE TABLE anomalies (
    id               UUID             PRIMARY KEY,
    window_id        BIGINT           NOT NULL UNIQUE REFERENCES detection_windows(id),
    service_id       INTEGER          NOT NULL REFERENCES services(id),
    model_id         INTEGER          NOT NULL REFERENCES model_registry(id),
    alert_id         UUID             REFERENCES alerts(id) ON DELETE SET NULL,
    detected_at      TIMESTAMPTZ      NOT NULL,
    window_start     TIMESTAMPTZ      NOT NULL,
    window_end       TIMESTAMPTZ      NOT NULL,
    anomaly_score    DOUBLE PRECISION NOT NULL CHECK (anomaly_score BETWEEN 0 AND 1),
    severity         VARCHAR(10)      NOT NULL
                     CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    summary          JSONB            NOT NULL DEFAULT '{}',
    sample_event_ids TEXT[]           NOT NULL DEFAULT '{}',
    feedback         VARCHAR(20)
                     CHECK (feedback IN ('CONFIRMED', 'FALSE_POSITIVE')),
    feedback_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE INDEX idx_anomalies_service_time  ON anomalies (service_id, detected_at DESC);
CREATE INDEX idx_anomalies_severity_time ON anomalies (severity, detected_at DESC);
CREATE INDEX idx_anomalies_alert         ON anomalies (alert_id);

-- ---------- seed data ----------
INSERT INTO services (name, description) VALUES
    ('api-gateway',       'Entry point; routes all requests'),
    ('auth-service',      'Login and token validation'),
    ('order-service',     'Order creation and lookup'),
    ('payment-service',   'Payment processing; depends on the database'),
    ('inventory-service', 'Stock checks and reservation');