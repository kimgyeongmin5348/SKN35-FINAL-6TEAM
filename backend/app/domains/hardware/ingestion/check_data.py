"""Read-only database checks and an export of the imported catalog."""

import re
from collections import Counter
from contextlib import closing

from app.core.parts_database import get_connection
from app.db.parts_schema import SCHEMA_PATH
from app.domains.hardware.ingestion.common import (
    DATA,
    TABLES,
    read_json,
    report,
    run_cli,
    write_json,
)
from app.domains.hardware.ingestion.import_parts import read_specs


def inspect_database(connection):
    errors, warnings, counts = [], [], {}
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    definitions = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\) ENGINE", sql, re.S)
    with connection.cursor(dictionary=True) as cursor:
        for table, definition in definitions:
            expected = re.findall(
                r"^    (\w+) (?:BIGINT|VARCHAR|CHAR|INT|TEXT|JSON|DECIMAL|DATETIME)\b",
                definition,
                re.M,
            )
            cursor.execute(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",
                (table,),
            )
            actual = [r["COLUMN_NAME"] for r in cursor.fetchall()]
            if actual != expected:
                errors.append({"table": table, "issue": "SCHEMA_COLUMNS_MISMATCH"})
        if errors:
            return {"passed": False, "errors": errors, "warnings": warnings}, []
        for table in TABLES:
            cursor.execute(f"SELECT COUNT(*) AS n FROM {table}")
            counts[table] = cursor.fetchone()["n"]
        cursor.execute(
            "SELECT TABLE_NAME,COUNT(*) AS n FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND CONSTRAINT_NAME='PRIMARY' GROUP BY TABLE_NAME"
        )
        for row in cursor.fetchall():
            if row["TABLE_NAME"] in TABLES and row["n"] != 1:
                errors.append({"table": row["TABLE_NAME"], "issue": "PRIMARY_KEY_NOT_INDEPENDENT"})
        cursor.execute("SELECT * FROM parts ORDER BY part_id")
        parts = cursor.fetchall()
        by_id = {p["part_id"]: p for p in parts}
        keys = []
        for p in parts:
            p["specs"] = read_specs(p["specs"])
            key = p["specs"].get("_provenance", {}).get("source_key")
            if key:
                keys.append(key)
        duplicate_keys = [k for k, n in Counter(keys).items() if n > 1]
        if duplicate_keys:
            errors.append({"issue": "DUPLICATE_SOURCE_KEYS", "keys": duplicate_keys})
        expected_keys = {
            m["source_key"]
            for m in read_json(DATA / "part_matches.json")["parts"]
            if m["import_enabled"]
        }
        if expected_keys - set(keys):
            errors.append(
                {"issue": "MISSING_SELECTED_PARTS", "keys": sorted(expected_keys - set(keys))}
            )
        cursor.execute("SELECT * FROM part_compatibility ORDER BY compatibility_id")
        evidence = cursor.fetchall()
        record_keys = []
        for row in evidence:
            conditions = read_specs(row["conditions"])
            a, b = by_id.get(row["part_a_id"]), by_id.get(row["part_b_id"])
            if not a or not b:
                errors.append({"issue": "ORPHAN_COMPATIBILITY", "id": row["compatibility_id"]})
                continue
            if key := conditions.get("_record_key"):
                record_keys.append(key)
            if row["check_type"] == "MEMORY_QVL":
                if b["model_number"] != conditions.get("ram_model_number"):
                    errors.append({"issue": "QVL_MPN_MISMATCH", "id": row["compatibility_id"]})
                if row["min_bios_version"] is not None:
                    errors.append(
                        {"issue": "QVL_TEST_BIOS_USED_AS_MINIMUM", "id": row["compatibility_id"]}
                    )
        expected_evidence = {
            r["record_key"]
            for r in read_json(DATA / "raw/manufacturer/compatibility_review.json")["records"]
        }
        if expected_evidence - set(record_keys):
            errors.append(
                {
                    "issue": "MISSING_REVIEWED_EVIDENCE",
                    "keys": sorted(expected_evidence - set(record_keys)),
                }
            )
        if any(n > 1 for n in Counter(record_keys).values()):
            errors.append({"issue": "DUPLICATE_EVIDENCE_KEYS"})
        cursor.execute(
            "SELECT q.quote_id,q.status,q.total_amount,COUNT(i.quote_item_id) AS item_count,SUM(i.unit_price IS NULL) AS unknown_prices,SUM(i.unit_price*i.quantity) AS component_total FROM quotes q LEFT JOIN quote_items i ON q.quote_id=i.quote_id GROUP BY q.quote_id,q.status,q.total_amount"
        )
        for row in cursor.fetchall():
            unknown = row["item_count"] == 0 or bool(row["unknown_prices"])
            total = row["total_amount"]
            if total is not None and (unknown or total != row["component_total"]):
                errors.append({"issue": "QUOTE_TOTAL_MISMATCH", "id": row["quote_id"]})
            if row["status"] == "CONFIRMED" and (unknown or total is None):
                errors.append({"issue": "CONFIRMED_QUOTE_INCOMPLETE", "id": row["quote_id"]})
        cursor.execute(
            "SELECT COUNT(*) AS n FROM quote_validations v JOIN quotes q ON q.quote_id=v.quote_id WHERE q.version<>v.quote_version"
        )
        if n := cursor.fetchone()["n"]:
            warnings.append({"issue": "HISTORICAL_VALIDATIONS_NOT_CURRENT", "count": n})
        missing_prices = [p["part_id"] for p in parts if p["current_price"] is None]
        if missing_prices:
            warnings.append({"issue": "PRICE_NOT_VERIFIED", "part_ids": missing_prices})
        return {
            "passed": not errors,
            "table_counts": counts,
            "errors": errors,
            "warnings": warnings,
            "evidence_by_type": dict(Counter(r["check_type"] for r in evidence)),
            "priced_parts": len(parts) - len(missing_prices),
            "unpriced_parts": len(missing_prices),
        }, parts


def main():
    with closing(get_connection()) as connection:
        result, parts = inspect_database(connection)
    write_json(DATA / "reports/catalog_snapshot.json", {"parts": parts})
    path = report("check-data", result)
    write_json(DATA / "reports/latest_check.json", {**result, "report_path": path.name})
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
