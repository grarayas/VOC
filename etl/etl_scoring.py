"""
ETL: Risk scoring — updates risk_score, likelihood, impact, asset_exposure, sla_tracking.

risk_score = f(cvss_v3_score, asset_criticality, asset_exposure)

  asset_criticality weight: Critical=1.0  Important=0.7  Standard=0.4
  asset_exposure:           0–100 (based on environment + VLAN zone)
  likelihood:               0.0–1.0 (CVSS / 10 * exploitability factor)
  impact:                   0.0–1.0 (criticality_weight * exposure / 100)

Run: python -m etl.etl_scoring
"""
import time
import sys
from datetime import date

import pyodbc

DB_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=VOC_DataBase;"
    "Trusted_Connection=yes;"
)

_CRITICALITY_WEIGHT = {
    'Critical':  1.0,
    'Important': 0.7,
    'Standard':  0.4,
}

_ENV_EXPOSURE = {
    'Production':  80.0,
    'Staging':     50.0,
    'Development': 20.0,
}

_SLA_AT_RISK_DAYS = 7  # flag "At Risk" when due in <= 7 days


def run():
    start = time.time()
    conn = pyodbc.connect(DB_CONN_STR)
    cursor = conn.cursor()
    log_id = _start_log(cursor, conn)

    try:
        rows = cursor.execute("""
            SELECT
                av.av_id, av.vuln_status,
                v.cvss_v3_score, v.exploitable, v.exploit_ease,
                a.criticality, a.environment,
                s.sla_id, s.sla_due_date, s.sla_status
            FROM asset_vulnerabilities av
            JOIN vulnerabilities v ON av.vuln_id = v.vuln_id
            JOIN assets a ON av.asset_id = a.asset_id
            LEFT JOIN sla_tracking s ON av.av_id = s.av_id
            WHERE av.vuln_status NOT IN ('Closed', 'Accepted Risk')
        """).fetchall()

        updated = 0
        today = date.today()

        for row in rows:
            av_id = row.av_id
            cvss = float(row.cvss_v3_score or 0)
            exploitable = bool(row.exploitable)
            exploit_ease = (row.exploit_ease or '').lower()
            criticality = row.criticality or 'Important'
            environment = row.environment or 'Production'

            crit_weight = _CRITICALITY_WEIGHT.get(criticality, 0.7)
            exposure = _ENV_EXPOSURE.get(environment, 50.0)

            exploitability = 1.3 if exploitable or 'exploit' in exploit_ease else 1.0
            likelihood = min((cvss / 10.0) * exploitability, 1.0)
            impact = min(crit_weight * (exposure / 100.0), 1.0)
            risk_score = round((likelihood * 0.5 + impact * 0.5) * cvss, 2)

            cursor.execute("""
                UPDATE asset_vulnerabilities SET
                    asset_exposure=?, likelihood=?, impact=?, risk_score=?
                WHERE av_id=?
            """, round(exposure, 2), round(likelihood, 4), round(impact, 4), risk_score, av_id)

            # Update SLA status
            if row.sla_id:
                due = row.sla_due_date
                current_sla = row.sla_status
                if current_sla == 'Completed':
                    pass  # don't touch completed
                elif due and today > due:
                    new_sla = 'Breached'
                elif due and (due - today).days <= _SLA_AT_RISK_DAYS:
                    new_sla = 'At Risk'
                else:
                    new_sla = 'On Track'

                if current_sla != new_sla:
                    cursor.execute(
                        "UPDATE sla_tracking SET sla_status=? WHERE sla_id=?",
                        new_sla, row.sla_id
                    )

            updated += 1

        conn.commit()
        duration = time.time() - start
        _finish_log(cursor, conn, log_id, 'success', updated, duration)
        print(f"Scoring ETL done: {updated} records updated in {duration:.1f}s")

    except Exception as exc:
        conn.rollback()
        _finish_log(cursor, conn, log_id, 'error', 0, time.time() - start, error_msg=str(exc))
        print(f"Scoring ETL error: {exc}", file=sys.stderr)
        raise
    finally:
        conn.close()


def _start_log(cursor, conn) -> int:
    cursor.execute(
        "INSERT INTO etl_logs (source, status, run_at) OUTPUT INSERTED.log_id VALUES ('scoring', 'running', GETDATE())"
    )
    log_id = cursor.fetchone()[0]
    conn.commit()
    return log_id


def _finish_log(cursor, conn, log_id, status, records=0, duration=0, error_msg=None):
    cursor.execute("""
        UPDATE etl_logs SET status=?, records_inserted=?, duration_sec=?, error_msg=?
        WHERE log_id=?
    """, status, records, round(duration, 2), error_msg, log_id)
    conn.commit()


if __name__ == '__main__':
    run()
