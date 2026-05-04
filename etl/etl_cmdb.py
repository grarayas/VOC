"""
ETL: CMDB → assets table.

Inputs:
  - Server_Usage_List.csv   → scope / BV info
  - All_Active_CIs.csv      → technical details (hostname, IP, OS, etc.)

Correlation key: ip_address (primary) → netbios_name → dns_name

Run:  python -m etl.etl_cmdb --server_usage <path> --active_cis <path>
"""
import argparse
import time
import sys
import pandas as pd
import pyodbc
from datetime import datetime

DB_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=VOC_DataBase;"
    "Trusted_Connection=yes;"
)


def run(server_usage_path: str, active_cis_path: str):
    start = time.time()
    conn = pyodbc.connect(DB_CONN_STR)
    cursor = conn.cursor()

    log_id = _start_log(cursor, conn, source='cmdb')

    try:
        df_su = pd.read_csv(server_usage_path, dtype=str).fillna('')
        df_ci = pd.read_csv(active_cis_path, dtype=str).fillna('')

        # Normalize column names
        df_su.columns = [c.strip().lower().replace(' ', '_') for c in df_su.columns]
        df_ci.columns = [c.strip().lower().replace(' ', '_') for c in df_ci.columns]

        # Merge on IP (adapt column names to match your actual CSV headers)
        df = df_ci.merge(df_su, on='ip_address', how='left', suffixes=('', '_su'))

        extracted = len(df)
        inserted = matched = skipped = 0

        scope_cache = _build_scope_cache(cursor)

        for _, row in df.iterrows():
            scope_id = _resolve_scope(row, scope_cache)
            if scope_id is None:
                skipped += 1
                continue

            ip = row.get('ip_address', '').strip()
            name = row.get('name', row.get('hostname', '')).strip()
            if not name:
                skipped += 1
                continue

            existing = cursor.execute(
                "SELECT asset_id FROM assets WHERE ip_address = ? OR name = ?", ip, name
            ).fetchone()

            asset_data = {
                'inventory_number': row.get('inventory_number', '').strip() or None,
                'rec_id':           row.get('rec_id', '').strip() or None,
                'ci_class':         row.get('ci_class', '').strip() or None,
                'ci_type':          row.get('ci_type', '').strip() or None,
                'name':             name,
                'ip_address':       ip or None,
                'mac_address':      row.get('mac_address', '').strip() or None,
                'operating_system': row.get('operating_system', '').strip() or None,
                'server_usage':     row.get('server_usage', '').strip() or None,
                'status':           row.get('status', 'Active').strip() or 'Active',
                'environment':      row.get('environment', '').strip() or None,
                'trigramm':         row.get('trigramm', '').strip() or None,
                'vlan':             row.get('vlan', '').strip() or None,
                'subnet_id':        row.get('subnet_id', '').strip() or None,
                'architecture':     row.get('architecture', '').strip() or None,
                'criticality':      row.get('criticality', 'Important').strip() or 'Important',
                'app_name':         row.get('app_name', '').strip() or None,
                'dev_team':         row.get('dev_team', '').strip() or None,
                'it_team':          row.get('it_team', '').strip() or None,
                'last_synced_at':   datetime.utcnow(),
                'scope_id':         scope_id,
            }

            if existing:
                matched += 1
                cursor.execute("""
                    UPDATE assets SET
                        ip_address=?, operating_system=?, status=?, environment=?,
                        criticality=?, last_synced_at=?, scope_id=?
                    WHERE asset_id=?
                """, asset_data['ip_address'], asset_data['operating_system'],
                    asset_data['status'], asset_data['environment'],
                    asset_data['criticality'], asset_data['last_synced_at'],
                    asset_data['scope_id'], existing[0])
            else:
                cursor.execute("""
                    INSERT INTO assets (inventory_number, rec_id, ci_class, ci_type, name,
                        ip_address, mac_address, operating_system, server_usage, status,
                        environment, trigramm, vlan, subnet_id, architecture, criticality,
                        app_name, dev_team, it_team, last_synced_at, scope_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, *asset_data.values())
                inserted += 1

        conn.commit()
        _finish_log(cursor, conn, log_id, 'success', extracted, matched, inserted, skipped,
                    duration=time.time() - start)
        print(f"CMDB ETL done: {extracted} rows | {inserted} inserted | {matched} updated | {skipped} skipped")

    except Exception as exc:
        conn.rollback()
        _finish_log(cursor, conn, log_id, 'error', error_msg=str(exc), duration=time.time() - start)
        print(f"CMDB ETL error: {exc}", file=sys.stderr)
        raise
    finally:
        conn.close()


def _build_scope_cache(cursor) -> dict:
    rows = cursor.execute("SELECT scope_id, bv_name, scope_name FROM scopes").fetchall()
    return {r.bv_name: r.scope_id for r in rows if r.bv_name}


def _resolve_scope(row, cache: dict) -> int | None:
    bv = row.get('bv_name', '').strip()
    return cache.get(bv)


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
    parser.add_argument('--server_usage', required=True)
    parser.add_argument('--active_cis', required=True)
    args = parser.parse_args()
    run(args.server_usage, args.active_cis)
