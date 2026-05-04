"""
ETL: Tenable CSV export → vulnerabilities + asset_vulnerabilities.

vuln_id format: {ip_address}PL{plugin_id}PO{port}
Asset matching priority: ip_address → netbios_name → dns_name

Run:  python -m etl.etl_tenable --input <tenable_export.csv>
"""
import argparse
import time
import sys
from datetime import date, timedelta

import pandas as pd
import pyodbc

DB_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=VOC_DataBase;"
    "Trusted_Connection=yes;"
)

_SLA_DAYS = {'Critical': 15, 'High': 30, 'Medium': 90, 'Low': 90, 'Info': 180}

# Map Tenable CSV column names to our model field names
TENABLE_COL_MAP = {
    'Plugin ID':               'plugin_id',
    'Plugin Name':             'plugin_name',
    'CVE':                     'cve',
    'Family':                  'family',
    'Synopsis':                'synopsis',
    'Description':             'description',
    'Plugin Output':           'plugin_output',
    'Solution':                'steps_to_remediate',
    'See Also':                'see_also',
    'CPE':                     'cpe',
    'Check Type':              'check_type',
    'Exploit Frameworks':      'exploit_frameworks',
    'Exploit Ease':            'exploit_ease',
    'Exploitable':             'exploitable',
    'CVSS V2 Base Score':      'cvss_v2_score',
    'CVSS V3 Base Score':      'cvss_v3_score',
    'Risk':                    'severity',
    'Vulnerability Published': 'vuln_publication_date',
    'Patch Published':         'patch_publication_date',
    'Plugin Published':        'plugin_publication_date',
    'Plugin Modified':         'plugin_modification_date',
    'IP Address':              'ip_address',
    'NetBIOS Name':            'netbios_name',
    'DNS Name':                'dns_name',
    'Port':                    'port',
    'First Discovered':        'first_discovered',
    'Last Observed':           'last_observed',
}


def run(csv_path: str):
    start = time.time()
    conn = pyodbc.connect(DB_CONN_STR)
    cursor = conn.cursor()
    log_id = _start_log(cursor, conn, 'tenable')

    try:
        df = pd.read_csv(csv_path, dtype=str).fillna('')
        df.rename(columns=TENABLE_COL_MAP, inplace=True)

        extracted = len(df)
        matched = inserted = skipped = 0

        asset_cache = _build_asset_cache(cursor)

        for _, row in df.iterrows():
            ip = row.get('ip_address', '').strip()
            netbios = row.get('netbios_name', '').strip()
            dns = row.get('dns_name', '').strip()
            plugin_id = row.get('plugin_id', '').strip()
            port = row.get('port', '0').strip() or '0'
            severity = row.get('severity', 'Medium').strip()

            vuln_id = f"{ip}PL{plugin_id}PO{port}"

            asset_id = (asset_cache.get(ip)
                        or asset_cache.get(netbios)
                        or asset_cache.get(dns))
            if not asset_id:
                skipped += 1
                continue

            matched += 1
            _upsert_vulnerability(cursor, row, vuln_id)

            existing_av = cursor.execute(
                "SELECT av_id FROM asset_vulnerabilities WHERE vuln_id=? AND asset_id=?",
                vuln_id, asset_id
            ).fetchone()

            if existing_av:
                # Update last_observed only
                cursor.execute(
                    "UPDATE asset_vulnerabilities SET last_observed=? WHERE av_id=?",
                    _parse_date(row.get('last_observed', '')), existing_av[0]
                )
            else:
                fd = _parse_date(row.get('first_discovered', '')) or date.today()
                cursor.execute("""
                    INSERT INTO asset_vulnerabilities
                        (vuln_id, asset_id, source, ip_address, netbios_name, dns_name,
                         port, first_discovered, last_observed, vuln_status)
                    VALUES (?,?,?,?,?,?,?,?,?,'Open')
                """, vuln_id, asset_id, 'tenable', ip or None, netbios or None, dns or None,
                    int(port) if port.isdigit() else None,
                    fd, _parse_date(row.get('last_observed', '')) or fd)

                av_id = cursor.execute(
                    "SELECT TOP 1 av_id FROM asset_vulnerabilities WHERE vuln_id=? AND asset_id=? ORDER BY av_id DESC",
                    vuln_id, asset_id
                ).fetchone()[0]

                sla_days = _SLA_DAYS.get(severity, 90)
                cursor.execute("""
                    INSERT INTO sla_tracking (av_id, sla_days_target, sla_due_date, sla_status)
                    VALUES (?,?,?,?)
                """, av_id, sla_days, fd + timedelta(days=sla_days), 'On Track')

                inserted += 1

        conn.commit()
        _finish_log(cursor, conn, log_id, 'success', extracted, matched, inserted, skipped,
                    duration=time.time() - start)
        print(f"Tenable ETL done: {extracted} | matched={matched} | inserted={inserted} | skipped={skipped}")

    except Exception as exc:
        conn.rollback()
        _finish_log(cursor, conn, log_id, 'error', error_msg=str(exc), duration=time.time() - start)
        print(f"Tenable ETL error: {exc}", file=sys.stderr)
        raise
    finally:
        conn.close()


def _build_asset_cache(cursor) -> dict:
    """Returns {ip/netbios/dns → asset_id} lookup."""
    rows = cursor.execute("SELECT asset_id, ip_address, name FROM assets").fetchall()
    cache = {}
    for r in rows:
        if r.ip_address:
            cache[r.ip_address.strip()] = r.asset_id
        if r.name:
            cache[r.name.strip()] = r.asset_id
    return cache


def _upsert_vulnerability(cursor, row, vuln_id: str):
    exists = cursor.execute("SELECT 1 FROM vulnerabilities WHERE vuln_id=?", vuln_id).fetchone()
    if exists:
        return
    cursor.execute("""
        INSERT INTO vulnerabilities
            (vuln_id, plugin_id, plugin_name, cve, family, synopsis, description,
             plugin_output, steps_to_remediate, see_also, cpe, check_type,
             exploit_frameworks, exploit_ease, exploitable,
             cvss_v2_score, cvss_v3_score, severity,
             vuln_publication_date, patch_publication_date,
             plugin_publication_date, plugin_modification_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,
        vuln_id,
        row.get('plugin_id') or None,
        row.get('plugin_name') or None,
        row.get('cve') or None,
        row.get('family') or None,
        row.get('synopsis') or None,
        row.get('description') or None,
        row.get('plugin_output') or None,
        row.get('steps_to_remediate') or None,
        row.get('see_also') or None,
        row.get('cpe') or None,
        row.get('check_type') or None,
        row.get('exploit_frameworks') or None,
        row.get('exploit_ease') or None,
        1 if str(row.get('exploitable', '')).lower() in ('true', '1', 'yes') else 0,
        _parse_decimal(row.get('cvss_v2_score')),
        _parse_decimal(row.get('cvss_v3_score')),
        row.get('severity') or None,
        _parse_date(row.get('vuln_publication_date')),
        _parse_date(row.get('patch_publication_date')),
        _parse_date(row.get('plugin_publication_date')),
        _parse_date(row.get('plugin_modification_date')),
    )


def _parse_date(val):
    if not val or not str(val).strip():
        return None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            from datetime import datetime
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(val):
    try:
        return float(val) if val else None
    except (ValueError, TypeError):
        return None


def _start_log(cursor, conn, source) -> int:
    cursor.execute(
        "INSERT INTO etl_logs (source, status, run_at) OUTPUT INSERTED.log_id VALUES (?, 'running', GETDATE())",
        source
    )
    log_id = cursor.fetchone()[0]
    conn.commit()
    return log_id


def _finish_log(cursor, conn, log_id, status, extracted=0, matched=0, inserted=0, skipped=0,
                error_msg=None, duration=0):
    cursor.execute("""
        UPDATE etl_logs SET
            status=?, records_extracted=?, records_matched=?, records_inserted=?,
            records_skipped=?, error_msg=?, duration_sec=?
        WHERE log_id=?
    """, status, extracted, matched, inserted, skipped, error_msg, round(duration, 2), log_id)
    conn.commit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    args = parser.parse_args()
    run(args.input)
