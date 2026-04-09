-- 001_initial_schema.sql
-- Initial schema for FESI Phase 0.
-- ML-ready: signals table holds full feature vector at time of signal creation
-- (point-in-time correct).

PRAGMA foreign_keys = ON;

-- ============================================================================
-- raw_items: every fetched item from any source, before normalization.
-- ============================================================================
CREATE TABLE raw_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    fetched_at      TEXT NOT NULL,
    published_at    TEXT,
    url             TEXT,
    title           TEXT,
    raw_payload     TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    UNIQUE(source, source_id)
);

CREATE INDEX idx_raw_items_fetched ON raw_items(fetched_at);
CREATE INDEX idx_raw_items_published ON raw_items(published_at);
CREATE INDEX idx_raw_items_hash ON raw_items(content_hash);


-- ============================================================================
-- tickers: master list of tradeable instruments.
-- ============================================================================
CREATE TABLE tickers (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol                  TEXT NOT NULL,
    exchange                TEXT NOT NULL,
    name                    TEXT NOT NULL,
    sector                  TEXT,
    sub_sector              TEXT,
    market_cap_usd          REAL,
    country                 TEXT,
    is_watchlist            INTEGER NOT NULL DEFAULT 0,
    watchlist_thesis        TEXT,
    alert_min_conviction    INTEGER DEFAULT 3,
    added_at                TEXT NOT NULL,
    UNIQUE(symbol, exchange)
);

CREATE INDEX idx_tickers_symbol ON tickers(symbol);
CREATE INDEX idx_tickers_watchlist ON tickers(is_watchlist);


-- ============================================================================
-- signals: normalized + classified events. ML-ready feature vector frozen
-- at signal creation time.
-- ============================================================================
CREATE TABLE signals (
    id                                  INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identity
    created_at                          TEXT NOT NULL,
    event_at                            TEXT NOT NULL,

    -- Linkage
    primary_ticker_id                   INTEGER,
    catalyst_type                       TEXT NOT NULL,
    sector                              TEXT NOT NULL,

    -- Content
    headline                            TEXT NOT NULL,
    summary                             TEXT NOT NULL,
    economics_summary                   TEXT,

    -- Scoring (LLM v1 in Phase 1; later replaced/augmented by ML in Phase 3)
    impact_score                        INTEGER NOT NULL CHECK (impact_score BETWEEN 1 AND 5),
    probability_score                   INTEGER NOT NULL CHECK (probability_score BETWEEN 1 AND 5),
    conviction_score                    REAL NOT NULL,
    timeframe_bucket                    TEXT NOT NULL,
    direction                           TEXT NOT NULL DEFAULT 'bullish',

    -- ML feature vector (frozen at creation)
    feature_source_count                INTEGER,
    feature_source_diversity            INTEGER,
    feature_source_quality_avg          REAL,
    feature_sentiment_score             REAL,
    feature_market_cap_bucket           TEXT,
    feature_market_cap_usd              REAL,
    feature_time_of_day                 TEXT,
    feature_day_of_week                 INTEGER,
    feature_is_watchlist                INTEGER,
    feature_catalyst_prior_hit_rate     REAL,
    feature_catalyst_prior_avg_return   REAL,
    feature_embedding_id                INTEGER,

    -- Source materials (JSON arrays)
    raw_item_ids                        TEXT,
    source_urls                         TEXT,

    -- Status
    status                              TEXT NOT NULL DEFAULT 'active',

    FOREIGN KEY (primary_ticker_id) REFERENCES tickers(id)
);

CREATE INDEX idx_signals_created ON signals(created_at);
CREATE INDEX idx_signals_event ON signals(event_at);
CREATE INDEX idx_signals_ticker ON signals(primary_ticker_id);
CREATE INDEX idx_signals_catalyst ON signals(catalyst_type);
CREATE INDEX idx_signals_sector ON signals(sector);
CREATE INDEX idx_signals_conviction ON signals(conviction_score);
CREATE INDEX idx_signals_status ON signals(status);


-- ============================================================================
-- decisions: every shadow (and eventually live) decision the system made.
-- ============================================================================
CREATE TABLE decisions (
    id                                  INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id                           INTEGER NOT NULL,
    decided_at                          TEXT NOT NULL,
    mode                                TEXT NOT NULL CHECK (mode IN ('shadow','paper','live')),
    action                              TEXT NOT NULL CHECK (action IN ('buy','no_buy','sell','hold')),

    -- Buy intent
    intended_position_usd               REAL,
    intended_shares                     INTEGER,
    intended_entry_price                REAL,
    intended_stop_loss                  REAL,
    intended_target                     REAL,
    intended_holding_period_days        INTEGER,

    -- Reasoning
    rule_triggered                      TEXT,
    reasoning                           TEXT NOT NULL,
    confidence                          REAL NOT NULL,

    -- Risk gates (each must pass for any 'buy' to proceed)
    passed_position_size_check          INTEGER NOT NULL,
    passed_concurrent_check             INTEGER NOT NULL,
    passed_sector_concentration_check   INTEGER NOT NULL,
    passed_circuit_breaker_check        INTEGER NOT NULL,

    FOREIGN KEY (signal_id) REFERENCES signals(id)
);

CREATE INDEX idx_decisions_signal ON decisions(signal_id);
CREATE INDEX idx_decisions_decided ON decisions(decided_at);
CREATE INDEX idx_decisions_mode_action ON decisions(mode, action);


-- ============================================================================
-- trades: actual executions (paper or live).
-- ============================================================================
CREATE TABLE trades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id         INTEGER NOT NULL,
    mode                TEXT NOT NULL,
    side                TEXT NOT NULL CHECK (side IN ('buy','sell')),
    ticker_id           INTEGER NOT NULL,

    submitted_at        TEXT NOT NULL,
    filled_at           TEXT,

    requested_shares    INTEGER NOT NULL,
    filled_shares       INTEGER,
    requested_price     REAL,
    filled_price        REAL,

    broker_order_id     TEXT,
    status              TEXT NOT NULL,
    fees_usd            REAL DEFAULT 0,

    FOREIGN KEY (decision_id) REFERENCES decisions(id),
    FOREIGN KEY (ticker_id) REFERENCES tickers(id)
);

CREATE INDEX idx_trades_decision ON trades(decision_id);
CREATE INDEX idx_trades_ticker ON trades(ticker_id);
CREATE INDEX idx_trades_mode_status ON trades(mode, status);


-- ============================================================================
-- outcomes: joins signals to realized P&L for ML training & backtest.
-- ============================================================================
CREATE TABLE outcomes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id           INTEGER NOT NULL UNIQUE,

    price_at_signal     REAL,
    price_t1            REAL,
    price_t5            REAL,
    price_t30           REAL,
    price_t90           REAL,

    return_t1           REAL,
    return_t5           REAL,
    return_t30          REAL,
    return_t90          REAL,

    max_drawup_30d      REAL,
    max_drawdown_30d    REAL,

    last_updated_at     TEXT NOT NULL,
    is_mature           INTEGER NOT NULL DEFAULT 0,

    FOREIGN KEY (signal_id) REFERENCES signals(id)
);

CREATE INDEX idx_outcomes_mature ON outcomes(is_mature);


-- ============================================================================
-- prices: OHLCV cache (one row per ticker per day).
-- ============================================================================
CREATE TABLE prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_id   INTEGER NOT NULL,
    date        TEXT NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL NOT NULL,
    volume      INTEGER,
    source      TEXT NOT NULL,
    UNIQUE(ticker_id, date),
    FOREIGN KEY (ticker_id) REFERENCES tickers(id)
);

CREATE INDEX idx_prices_ticker_date ON prices(ticker_id, date);


-- ============================================================================
-- embeddings: text vectors for semantic dedupe and ML.
-- ============================================================================
CREATE TABLE embeddings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text_hash   TEXT NOT NULL UNIQUE,
    model       TEXT NOT NULL,
    vector      BLOB NOT NULL,
    created_at  TEXT NOT NULL
);


-- ============================================================================
-- catalyst_priors: historical baselines per catalyst type, learned from
-- accumulated outcomes data. Updated periodically by a job.
-- ============================================================================
CREATE TABLE catalyst_priors (
    catalyst_type       TEXT PRIMARY KEY,
    sample_size         INTEGER NOT NULL,
    hit_rate            REAL,
    avg_return_t1       REAL,
    avg_return_t5       REAL,
    avg_return_t30      REAL,
    avg_max_drawup      REAL,
    avg_max_drawdown    REAL,
    updated_at          TEXT NOT NULL
);


-- ============================================================================
-- digests: every digest sent (for journaling and audit).
-- ============================================================================
CREATE TABLE digests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at             TEXT NOT NULL,
    scan_window_start   TEXT NOT NULL,
    scan_window_end     TEXT NOT NULL,
    signal_count        INTEGER NOT NULL,
    decision_count      INTEGER NOT NULL,
    delivered_via       TEXT NOT NULL,
    markdown_body       TEXT NOT NULL
);

CREATE INDEX idx_digests_sent ON digests(sent_at);
