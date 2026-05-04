-- VOC Platform — Database Schema v2
-- Run in SSMS against VOC_DataBase
-- Order matters: parent tables before child tables

USE VOC_DataBase;
GO

-- ─────────────────────────────────────────────
-- 1. scopes
-- ─────────────────────────────────────────────
CREATE TABLE scopes (
    scope_id    INT IDENTITY(1,1) PRIMARY KEY,
    scope_name  NVARCHAR(150) NOT NULL,
    category    NVARCHAR(50)  NOT NULL,   -- 'applicatif' | 'systeme' | 'systeme_app'
    bv_name     NVARCHAR(150) NULL,
    description NVARCHAR(255) NULL
);
GO

-- ─────────────────────────────────────────────
-- 2. users
-- ─────────────────────────────────────────────
CREATE TABLE users (
    user_id   INT IDENTITY(1,1) PRIMARY KEY,
    username  NVARCHAR(100) NOT NULL UNIQUE,
    email     NVARCHAR(150) NOT NULL UNIQUE,
    role      NVARCHAR(50)  NOT NULL DEFAULT 'user',
    is_active BIT           NOT NULL DEFAULT 1,
    scope_id  INT           NOT NULL REFERENCES scopes(scope_id)
);
GO

-- ─────────────────────────────────────────────
-- 3. assets
-- ─────────────────────────────────────────────
CREATE TABLE assets (
    asset_id         INT IDENTITY(1,1) PRIMARY KEY,
    inventory_number NVARCHAR(100) NULL,
    rec_id           NVARCHAR(100) NULL,
    ci_class         NVARCHAR(100) NULL,
    ci_type          NVARCHAR(100) NULL,
    name             NVARCHAR(150) NOT NULL,
    ip_address       NVARCHAR(50)  NULL,
    mac_address      NVARCHAR(50)  NULL,
    operating_system NVARCHAR(150) NULL,
    server_usage     NVARCHAR(150) NULL,
    status           NVARCHAR(50)  DEFAULT 'Active',
    environment      NVARCHAR(100) NULL,
    trigramm         NVARCHAR(50)  NULL,
    vlan             NVARCHAR(50)  NULL,
    subnet_id        NVARCHAR(50)  NULL,
    architecture     NVARCHAR(100) NULL,
    criticality      NVARCHAR(50)  DEFAULT 'Important',
    app_name         NVARCHAR(150) NULL,
    dev_team         NVARCHAR(100) NULL,
    it_team          NVARCHAR(100) NULL,
    last_synced_at   DATETIME      NULL,
    scope_id         INT           NOT NULL REFERENCES scopes(scope_id)
);
GO

-- ─────────────────────────────────────────────
-- 4. vulnerabilities
-- ─────────────────────────────────────────────
CREATE TABLE vulnerabilities (
    vuln_id                  NVARCHAR(200) PRIMARY KEY,
    plugin_id                NVARCHAR(50)   NULL,
    plugin_name              NVARCHAR(255)  NULL,
    cve                      NVARCHAR(100)  NULL,
    family                   NVARCHAR(100)  NULL,
    synopsis                 NVARCHAR(500)  NULL,
    description              NVARCHAR(MAX)  NULL,
    plugin_output            NVARCHAR(MAX)  NULL,
    steps_to_remediate       NVARCHAR(MAX)  NULL,
    see_also                 NVARCHAR(500)  NULL,
    cpe                      NVARCHAR(255)  NULL,
    check_type               NVARCHAR(100)  NULL,
    exploit_frameworks       NVARCHAR(255)  NULL,
    exploit_ease             NVARCHAR(100)  NULL,
    exploitable              BIT            DEFAULT 0,
    cvss_v2_score            DECIMAL(4,1)   NULL,
    cvss_v3_score            DECIMAL(4,1)   NULL,
    severity                 NVARCHAR(50)   NULL,
    vuln_publication_date    DATE           NULL,
    patch_publication_date   DATE           NULL,
    plugin_publication_date  DATE           NULL,
    plugin_modification_date DATE           NULL
);
GO

-- ─────────────────────────────────────────────
-- 5. asset_vulnerabilities  (central table)
-- ─────────────────────────────────────────────
CREATE TABLE asset_vulnerabilities (
    av_id                INT IDENTITY(1,1) PRIMARY KEY,
    vuln_id              NVARCHAR(200) NOT NULL REFERENCES vulnerabilities(vuln_id),
    asset_id             INT           NOT NULL REFERENCES assets(asset_id),
    source               NVARCHAR(50)  NOT NULL DEFAULT 'tenable',
    ip_address           NVARCHAR(50)  NULL,
    netbios_name         NVARCHAR(150) NULL,
    dns_name             NVARCHAR(150) NULL,
    port                 INT           NULL,
    first_discovered     DATE          NULL,
    last_observed        DATE          NULL,

    vuln_status          NVARCHAR(50)  NOT NULL DEFAULT 'Open',
    branch               NVARCHAR(30)  NULL,

    vuln_type            NVARCHAR(100) NULL,
    vul_scope            NVARCHAR(150) NULL,
    reassigned_scope     NVARCHAR(150) NULL,
    asset_exposure       DECIMAL(5,2)  NULL,
    likelihood           DECIMAL(5,2)  NULL,
    impact               DECIMAL(5,2)  NULL,
    risk_score           DECIMAL(5,2)  NULL,
    remediation_strategy NVARCHAR(100) NULL,
    action_plan_provided BIT           NOT NULL DEFAULT 0,
    created_at           DATETIME      NOT NULL DEFAULT GETDATE(),
    updated_at           DATETIME      NOT NULL DEFAULT GETDATE()
);
GO

-- Trigger to auto-update updated_at
CREATE TRIGGER trg_av_updated_at
ON asset_vulnerabilities
AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    UPDATE asset_vulnerabilities
    SET updated_at = GETDATE()
    WHERE av_id IN (SELECT av_id FROM inserted);
END;
GO

-- ─────────────────────────────────────────────
-- 6. sla_tracking
-- ─────────────────────────────────────────────
CREATE TABLE sla_tracking (
    sla_id            INT IDENTITY(1,1) PRIMARY KEY,
    av_id             INT          NOT NULL UNIQUE REFERENCES asset_vulnerabilities(av_id),
    sla_days_target   INT          NULL,
    sla_due_date      DATE         NULL,
    sla_status        NVARCHAR(50) DEFAULT 'On Track',
    remed_target_date DATE         NULL,
    risk_acceptance   BIT          NOT NULL DEFAULT 0,
    remed_responsible INT          NULL REFERENCES users(user_id)
);
GO

-- ─────────────────────────────────────────────
-- 7. vuln_history
-- ─────────────────────────────────────────────
CREATE TABLE vuln_history (
    history_id INT IDENTITY(1,1) PRIMARY KEY,
    av_id      INT           NOT NULL REFERENCES asset_vulnerabilities(av_id),
    user_id    INT           NOT NULL REFERENCES users(user_id),
    entry_type NVARCHAR(30)  NOT NULL,   -- 'status_change' | 'comment'
    old_status NVARCHAR(50)  NULL,
    new_status NVARCHAR(50)  NULL,
    content    NVARCHAR(MAX) NULL,
    created_at DATETIME      NOT NULL DEFAULT GETDATE()
);
GO

-- ─────────────────────────────────────────────
-- 8. etl_logs
-- ─────────────────────────────────────────────
CREATE TABLE etl_logs (
    log_id            INT IDENTITY(1,1) PRIMARY KEY,
    source            NVARCHAR(50)  NULL,
    status            NVARCHAR(20)  DEFAULT 'running',
    records_extracted INT           DEFAULT 0,
    records_matched   INT           DEFAULT 0,
    records_inserted  INT           DEFAULT 0,
    records_skipped   INT           DEFAULT 0,
    error_msg         NVARCHAR(MAX) NULL,
    duration_sec      DECIMAL(8,2)  NULL,
    run_at            DATETIME      NOT NULL DEFAULT GETDATE()
);
GO

-- ─────────────────────────────────────────────
-- Indexes for frequent query patterns
-- ─────────────────────────────────────────────
CREATE INDEX ix_av_asset_id     ON asset_vulnerabilities(asset_id);
CREATE INDEX ix_av_vuln_id      ON asset_vulnerabilities(vuln_id);
CREATE INDEX ix_av_status       ON asset_vulnerabilities(vuln_status);
CREATE INDEX ix_av_source       ON asset_vulnerabilities(source);
CREATE INDEX ix_assets_ip       ON assets(ip_address);
CREATE INDEX ix_assets_scope    ON assets(scope_id);
CREATE INDEX ix_sla_status      ON sla_tracking(sla_status);
CREATE INDEX ix_history_av_id   ON vuln_history(av_id);
GO
