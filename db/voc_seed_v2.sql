-- VOC Platform — Seed Data v2
-- Run AFTER voc_schema_v2.sql

USE VOC_DataBase;
GO

-- ─────────────────────────────────────────────
-- 20 Scopes
-- ─────────────────────────────────────────────
SET IDENTITY_INSERT scopes ON;
INSERT INTO scopes (scope_id, scope_name, category) VALUES
( 1, 'Digital Workspace',                    'applicatif'),
( 2, 'Cyber Security',                       'applicatif'),
( 3, 'ITAM',                                 'applicatif'),
( 4, 'IT Core Banking & Life Insurance',     'applicatif'),
( 5, 'IT Data & Corporate Functions',        'applicatif'),
( 6, 'IT Financial Control & PMO',           'applicatif'),
( 7, 'IT Governance',                        'applicatif'),
( 8, 'IT ICB',                               'applicatif'),
( 9, 'IT Markets',                           'applicatif'),
(10, 'IT Operations & Infrastructures',      'applicatif'),
(11, 'IT Payment & Compliance',              'applicatif'),
(12, 'IT PWM & IFA',                         'applicatif'),
(13, 'Software Development Factory',         'applicatif'),
(14, 'Other',                                'applicatif'),
(15, 'Datacenter Team',                      'systeme'),
(16, 'Linux Team',                           'systeme'),
(17, 'Windows Team',                         'systeme'),
(18, 'Network Team',                         'systeme'),
(19, 'Middleware & Tools',                   'systeme'),
(20, 'IT Operations & Infrastructures Ops',  'systeme_app');
SET IDENTITY_INSERT scopes OFF;
GO

-- ─────────────────────────────────────────────
-- Seed Users (dev/test accounts)
-- ─────────────────────────────────────────────
INSERT INTO users (username, email, role, is_active, scope_id) VALUES
('admin',         'admin@bank.local',         'admin', 1, 2),
('resp.cybersec', 'resp.cybersec@bank.local', 'user',  1, 2),
('resp.windows',  'resp.windows@bank.local',  'user',  1, 17),
('resp.linux',    'resp.linux@bank.local',    'user',  1, 16),
('resp.network',  'resp.network@bank.local',  'user',  1, 18),
('resp.dc',       'resp.dc@bank.local',       'user',  1, 15);
GO

-- ─────────────────────────────────────────────
-- Sample assets for testing
-- ─────────────────────────────────────────────
INSERT INTO assets (name, ip_address, ci_class, ci_type, operating_system, environment, criticality, scope_id) VALUES
('SRV-AD-001',   '10.30.3.10',   'Server', 'Physical', 'Windows Server 2019', 'Production', 'Critical',  17),
('SRV-WEB-001',  '10.20.13.10',  'Server', 'Virtual',  'Linux Ubuntu 22.04',  'Production', 'Important', 16),
('SRV-DB-001',   '10.20.2.11',   'Server', 'Virtual',  'Windows Server 2022', 'Production', 'Critical',  17),
('FW-CORE-001',  '10.10.1.1',    'Server', 'Firewall', 'Cisco IOS',           'Production', 'Critical',  18),
('SRV-DEV-001',  '192.168.1.10', 'Server', 'Virtual',  'Linux CentOS 8',      'Development','Standard',  13);
GO
