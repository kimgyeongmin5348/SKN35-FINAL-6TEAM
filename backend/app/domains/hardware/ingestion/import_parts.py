"""Normalize reviewed identities, then preview or transactionally import parts."""

import argparse
import html
import re
from contextlib import closing

from app.db.connection import get_connection
from app.domains.hardware.ingestion.common import (
    CATEGORIES,
    DATA,
    import_transaction,
    json_text,
    price_value,
    read_json,
    report,
    run_cli,
    sql_time,
    utc_now,
    write_json,
)


def clean_name(value):
    return " ".join(re.sub(r"<[^>]*>", "", html.unescape(value or "")).split())


def load_reviewed_specs():
    reviewed = read_json(DATA / "raw/manufacturer/pilot_specs_review.json")
    for key, fields in read_json(DATA / "reviewed_specs_overrides.json").items():
        part = reviewed["parts"].setdefault(key, {})
        sources = [*part.get("sources", []), *fields.get("sources", [])]
        part.update(fields)
        part["sources"] = list(dict.fromkeys(sources))
    return reviewed


def reviewed_price(match, observations):
    """Product code AND reviewed name must agree. Unreviewed delivery basis is withheld."""
    code = match.get("danawa_product_code")
    expected = match.get("expected_listing_name")
    if not code or not expected:
        return None, "NO_REVIEWED_LISTING"
    candidates = []
    for record in observations:
        if not (record.get("response") or {}).get("ok"):
            continue
        for item in record["response"].get("items", []):
            if str(item.get("productCode")) == code:
                candidates.append((record, item))
    if not candidates:
        return None, "LISTING_NOT_RETURNED"
    record, item = max(candidates, key=lambda pair: sql_time(pair[0]["queried_at_utc"]))
    if clean_name(item.get("productName")) != clean_name(expected):
        return None, "LISTING_NAME_CHANGED"
    price = price_value(item.get("minPrice"))
    if price is None:
        return None, "INVALID_PRICE"
    evidence = record.get("price_evidence") or {}
    if evidence.get("verified"):
        source_url = f"https://prod.danawa.com/info/?pcode={code}"
        page_price = price_value(evidence.get("component_price"))
        if (
            evidence.get("product_code") != code
            or evidence.get("source_url") != source_url
            or clean_name(evidence.get("product_name")) != clean_name(expected)
            or page_price is None
            or not evidence.get("checked_at_utc")
        ):
            return None, "PRICE_EVIDENCE_MISMATCH"
        sql_time(evidence["checked_at_utc"])
        return {
            "value": str(page_price),
            "source_url": source_url,
            "checked_at": evidence["checked_at_utc"],
        }, "VERIFIED_COMPONENT_PRICE"
    if match.get("price_basis") != "COMPONENT_ONLY" or not match.get("price_basis_source_url"):
        return None, "PRICE_BASIS_UNVERIFIED"
    return {
        "value": str(price),
        "source_url": f"https://prod.danawa.com/info/?pcode={code}",
        "checked_at": record["queried_at_utc"],
    }, "VERIFIED"


def normalize_parts(catalog, matches, reviewed_specs, observations, checked_at):
    origin = {
        row["id"]: (category, row) for category in CATEGORIES for row in catalog.get(category, [])
    }
    if len({row["source_key"] for row in matches}) != len(matches):
        raise ValueError("매칭 파일에 중복 source_key가 있습니다.")
    rows, withheld = [], []
    for match in matches:
        if not match["import_enabled"]:
            withheld.append({"source_key": match["source_key"], "reason": match["review_note"]})
            continue
        key = match["source_key"]
        if match["category"] not in CATEGORIES or not all(match.get(k) for k in ("brand", "name")):
            raise ValueError(f"{key}: 제품 식별 필드가 부족합니다.")
        original = origin.get(match.get("catalog_id"))
        if match.get("catalog_id") and original is None:
            raise ValueError(f"{key}: 원본 ID가 사라졌습니다. 검토가 필요합니다.")
        if original and original[0] != match["category"]:
            raise ValueError(f"{key}: 부품 분류가 원본과 다릅니다.")
        raw = original[1] if original else {}
        # Editorial recommendation labels are not treated as hardware facts.
        excluded = {
            "id",
            "vendor",
            "model",
            "source",
            "last_verified",
            "notes",
            "performance_tier",
            "use_cases",
        }
        specs = {k: v for k, v in raw.items() if k not in excluded}
        curated = reviewed_specs["parts"].get(key, {})
        for field, value in curated.items():
            if field not in ("sources", "supported_cpus", "bundled_cooler"):
                specs[field] = value
        # A cooler bundled with a chosen retail package is not a CPU-wide fact.
        if curated.get("bundled_cooler"):
            specs["listing_options"] = {
                "danawa_product_code": match.get("danawa_product_code"),
                "bundled_cooler": curated["bundled_cooler"],
            }
        specs.update(match.get("spec_overrides", {}))
        aliases = {
            "module_gb": "module_capacity_gb",
            "max_gpu_mm": "max_gpu_length_mm",
            "max_cooler_mm": "max_cpu_cooler_mm",
            "max_psu_mm": "max_psu_length_mm",
        }
        for old, new in aliases.items():
            if old in specs:
                specs[new] = specs.pop(old)
        if specs.get("form_factor") == "Micro-ATX":
            specs["form_factor"] = "mATX"
        if match["category"] == "psu":
            standard = re.fullmatch(r"ATX\s+(\d+\.\d+)", raw.get("form_factor", ""))
            if standard:
                specs["atx_version"] = standard[1]
                specs["form_factor"] = "ATX"
            if "gpu16" in curated and "pcie_5_connectors" in specs:
                # The original count mixes PSU-side sockets with bundled GPU cables.
                specs.pop("pcie_5_connectors")
        if match["category"] == "ram" and isinstance(specs.get("kit"), str):
            kit = re.fullmatch(r"(\d+)x(\d+)GB", specs["kit"])
            if kit:
                specs["modules_per_item"], specs["module_capacity_gb"] = map(int, kit.groups())
        sources = [reviewed_specs["sources"][s] for s in curated.get("sources", [])]
        primary_url = match.get("spec_source_url") or (
            sources[0]["url"] if sources else raw.get("source")
        )
        primary_url = (
            primary_url
            or "https://github.com/iBlessi/pc-builder-parts/blob/main/pc-builder-parts.json"
        )
        price, price_status = reviewed_price(match, observations)
        specs["_provenance"] = {
            "source_key": key,
            "catalog_id": match.get("catalog_id"),
            "catalog_version": catalog["_meta"].get("version"),
            "source_verified_on": raw.get("last_verified"),
            "reviewed_on": reviewed_specs["checked_on"],
            "review_status": match["review_status"],
            "review_note": match["review_note"],
            "spec_sources": sources,
            "danawa_product_code": match.get("danawa_product_code"),
            "price_status": price_status,
            "price_basis_source_url": price["source_url"]
            if price
            else match.get("price_basis_source_url"),
        }
        if "gpu16" in curated and "pcie_5_connectors" in raw:
            specs["_provenance"]["catalog_ambiguous_connector_count"] = raw["pcie_5_connectors"]
        rows.append(
            {
                "source_key": key,
                "category": match["category"],
                "brand": match["brand"],
                "name": match["name"],
                "model_number": match.get("model_number"),
                "specs": specs,
                "source_url": primary_url,
                "verified_at": checked_at,
                "current_price": price["value"] if price else None,
                "currency": "KRW",
                "price_source_url": price["source_url"] if price else None,
                "price_checked_at": price["checked_at"] if price else None,
            }
        )
    identities = [(r["category"], r["brand"], r["name"]) for r in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("중복 정규 제품명이 있습니다.")
    return rows, withheld


def upsert_parts(connection, rows):
    counts = {"inserted": 0, "updated": 0, "preserved_prices": 0}
    with connection.cursor(dictionary=True) as cursor:
        for row in rows:
            cursor.execute(
                "SELECT * FROM parts WHERE category=%s AND brand=%s AND name=%s FOR UPDATE",
                (row["category"], row["brand"], row["name"]),
            )
            existing = cursor.fetchone()
            price, price_url, price_time = (
                row["current_price"],
                row["price_source_url"],
                sql_time(row["price_checked_at"]),
            )
            if existing:
                old_specs = read_specs(existing["specs"])
                old_key = old_specs.get("_provenance", {}).get("source_key")
                if old_key and old_key != row["source_key"]:
                    raise ValueError(f"제품 식별 충돌: {row['source_key']}")
                if existing["model_number"] and existing["model_number"] != row["model_number"]:
                    raise ValueError(f"모델번호 변경은 수동 검토가 필요합니다: {row['source_key']}")
                if existing["current_price"] is not None and (
                    price is None
                    or (existing["price_checked_at"] and price_time < existing["price_checked_at"])
                ):
                    price, price_url, price_time = (
                        existing["current_price"],
                        existing["price_source_url"],
                        existing["price_checked_at"],
                    )
                    counts["preserved_prices"] += 1
            values = (
                row["model_number"],
                json_text(row["specs"]),
                row["source_url"],
                sql_time(row["verified_at"]),
                price,
                row["currency"],
                price_url,
                price_time,
            )
            if existing:
                cursor.execute(
                    "UPDATE parts SET model_number=%s,specs=%s,source_url=%s,verified_at=%s,current_price=%s,currency=%s,price_source_url=%s,price_checked_at=%s WHERE part_id=%s",
                    (*values, existing["part_id"]),
                )
                counts["updated"] += 1
            else:
                cursor.execute(
                    "INSERT INTO parts (category,brand,name,model_number,specs,source_url,verified_at,current_price,currency,price_source_url,price_checked_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (row["category"], row["brand"], row["name"], *values),
                )
                counts["inserted"] += 1
    return counts


def read_specs(value):
    import json

    return json.loads(value) if isinstance(value, str) else value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="실제 DB에 저장. 기본은 미리보기")
    args = parser.parse_args()
    manifest_path = DATA / "raw" / "collection_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    catalog_path = DATA / manifest.get("catalog", {}).get(
        "path", "raw/pc_builder/2026-11-11/pc-builder-parts.json"
    )
    observations = [read_json(DATA / r["path"]) for r in manifest.get("danawa", [])]
    rows, withheld = normalize_parts(
        read_json(catalog_path),
        read_json(DATA / "part_matches.json")["parts"],
        load_reviewed_specs(),
        observations,
        utc_now(),
    )
    write_json(
        DATA / "processed/parts.json",
        {"normalized_at_utc": utc_now(), "parts": rows, "withheld": withheld},
    )
    result = {
        "mode": "apply" if args.apply else "preview",
        "prepared": len(rows),
        "withheld": withheld,
        "missing_price_count": sum(row["current_price"] is None for row in rows),
    }
    if args.apply:
        with closing(get_connection()) as connection, import_transaction(connection):
            result.update(upsert_parts(connection, rows))
    report("import-parts", result)


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
