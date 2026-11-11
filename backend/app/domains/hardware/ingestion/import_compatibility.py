"""Import reviewed official evidence. Does not infer support from missing rows."""

import argparse
from contextlib import closing

from app.core.parts_database import get_connection
from app.domains.hardware.ingestion.common import (
    DATA,
    import_transaction,
    json_text,
    read_json,
    report,
    run_cli,
    sql_time,
    utc_now,
    write_json,
)
from app.domains.hardware.ingestion.import_parts import read_specs


def validate_records(records, matches):
    products = {m["source_key"]: m for m in matches if m["import_enabled"]}
    keys = set()
    for record in records:
        key = record["record_key"]
        if key in keys:
            raise ValueError("중복 호환성 근거 키: " + key)
        keys.add(key)
        a, b = products.get(record["part_a_key"]), products.get(record["part_b_key"])
        if not a or not b or a["category"] != "motherboard":
            raise ValueError(key + ": 기준 메인보드 또는 상대 부품이 없습니다.")
        kind = record["check_type"]
        if kind not in ("CPU_SUPPORT", "MEMORY_QVL", "KNOWN_CONFLICT"):
            raise ValueError(key + ": 알 수 없는 검사 유형입니다.")
        if kind == "CPU_SUPPORT" and b["category"] != "cpu":
            raise ValueError(key + ": CPU가 아닙니다.")
        if record["support_status"] not in ("SUPPORTED", "CONDITIONAL", "UNSUPPORTED"):
            raise ValueError(key + ": 지원 상태를 확인하세요.")
        scope, minimum = record["bios_scope"], record.get("min_bios_version")
        if scope not in ("ALL", "MIN_VERSION", "NOT_SPECIFIED") or (
            (scope == "MIN_VERSION") != bool(minimum)
        ):
            raise ValueError(key + ": 최소 BIOS 조건이 일관되지 않습니다.")
        if not record.get("source_url", "").startswith("https://") or not record.get(
            "source_publisher"
        ):
            raise ValueError(key + ": 공식 출처가 필요합니다.")
        if kind == "MEMORY_QVL":
            if (
                b["category"] != "ram"
                or not b["model_number"]
                or record["conditions"].get("ram_model_number") != b["model_number"]
            ):
                raise ValueError(key + ": RAM의 정확한 품번이 일치하지 않습니다.")
            if not record["conditions"].get("cpu_family"):
                raise ValueError(key + ": QVL의 CPU 계열이 필요합니다.")
            if scope != "NOT_SPECIFIED" or minimum:
                raise ValueError(key + ": 현재 QVL 원본은 최소 BIOS를 명시하지 않습니다.")
    return records


def upsert_compatibility(connection, records, checked_at):
    counts = {"inserted": 0, "updated": 0}
    with connection.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT part_id,model_number,specs FROM parts")
        products = {}
        for row in cursor.fetchall():
            key = read_specs(row["specs"]).get("_provenance", {}).get("source_key")
            if key:
                if key in products:
                    raise ValueError("DB 부품 원본 키가 중복됐습니다: " + key)
                products[key] = row
        for record in records:
            a, b = products.get(record["part_a_key"]), products.get(record["part_b_key"])
            if not a or not b:
                raise ValueError("부품을 먼저 저장하세요: " + record["record_key"])
            if (
                record["check_type"] == "MEMORY_QVL"
                and b["model_number"] != record["conditions"]["ram_model_number"]
            ):
                raise ValueError("DB RAM 품번과 QVL 품번이 다릅니다: " + record["record_key"])
            conditions = {
                **record["conditions"],
                "_record_key": record["record_key"],
                "evidence_checked_on": record["evidence_checked_on"],
                "evidence_kind": "manually_reviewed_transcription",
                "source_date_precision": "day" if record.get("source_updated_on") else None,
            }
            cursor.execute(
                "SELECT compatibility_id,conditions FROM part_compatibility WHERE part_a_id=%s AND part_b_id=%s AND check_type=%s FOR UPDATE",
                (a["part_id"], b["part_id"], record["check_type"]),
            )
            existing = [
                r
                for r in cursor.fetchall()
                if read_specs(r["conditions"]).get("_record_key") == record["record_key"]
            ]
            if len(existing) > 1:
                raise ValueError("DB 호환성 근거가 중복됐습니다: " + record["record_key"])
            source_date = record.get("source_updated_on")
            values = (
                record["support_status"],
                record["bios_scope"],
                record.get("min_bios_version"),
                json_text(conditions),
                record["source_publisher"],
                record["source_url"],
                source_date + " 00:00:00" if source_date else None,
                sql_time(checked_at),
            )
            if existing:
                cursor.execute(
                    "UPDATE part_compatibility SET support_status=%s,bios_scope=%s,min_bios_version=%s,conditions=%s,source_publisher=%s,source_url=%s,source_updated_at=%s,verified_at=%s WHERE compatibility_id=%s",
                    (*values, existing[0]["compatibility_id"]),
                )
                counts["updated"] += 1
            else:
                cursor.execute(
                    "INSERT INTO part_compatibility (part_a_id,part_b_id,check_type,support_status,bios_scope,min_bios_version,conditions,source_publisher,source_url,source_updated_at,verified_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (a["part_id"], b["part_id"], record["check_type"], *values),
                )
                counts["inserted"] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source = read_json(DATA / "raw/manufacturer/compatibility_review.json")
    records = validate_records(source["records"], read_json(DATA / "part_matches.json")["parts"])
    checked_at = utc_now()
    write_json(
        DATA / "processed/compatibility.json", {"normalized_at_utc": checked_at, "records": records}
    )
    result = {"mode": "apply" if args.apply else "preview", "prepared": len(records)}
    if args.apply:
        with closing(get_connection()) as connection, import_transaction(connection):
            result.update(upsert_compatibility(connection, records, checked_at))
    report("import-compatibility", result)


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
