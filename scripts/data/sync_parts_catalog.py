#!/usr/bin/env python3
"""
sync_parts_catalog.py
---------------------
1. iBlessi/pc-builder-parts 최신 JSON 데이터셋 다운로드 (data/raw/pc-builder-parts.json)
2. tellang/danawa-cli를 사용하여 각 부품의 한국 다나와 최저가(KRW) 및 상품코드(pcode) 매핑
3. 통합 카탈로그 테이블 생성:
   - JSON (data/processed/parts_catalog.json)
   - CSV (data/processed/parts_catalog.csv)
   - SQLite DB (data/processed/parts_catalog.db -> parts_catalog & compatibility_rules 테이블)

사용 예시:
  # 카테고리당 3개씩 샘플 프로토타입 생성 (빠른 테스트)
  python scripts/data/sync_parts_catalog.py --sample-per-category 3

  # 전체 126개 부품 동기화 (약 2~3분 소요)
  python scripts/data/sync_parts_catalog.py --all

  # 이미 매핑된 pcode는 재검색하지 않고 가격만 갱신하거나 신규 부품만 매핑
  python scripts/data/sync_parts_catalog.py --all --use-cache
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import random
import re
import sqlite3
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

PC_BUILDER_PARTS_URL = (
    "https://raw.githubusercontent.com/iBlessi/pc-builder-parts/main/pc-builder-parts.json"
)

CATEGORIES = ["cpu", "gpu", "motherboard", "ram", "storage", "psu", "case"]

# 다나와 대분류/중분류 카테고리 prefix (완제품 PC나 엉뚱한 부품이 매칭되는 현상 방지)
DANAWA_CATEGORY_PREFIX: dict[str, tuple[str, ...]] = {
    "cpu": ("861|873|",),
    "gpu": ("861|876|",),
    "motherboard": ("861|875|",),
    "ram": ("861|874|",),
    "storage": ("861|32617|", "861|877|"),
    "psu": ("861|880|",),
    "case": ("861|879|",),
}


def strip_html(text: str) -> str:
    """<b> 태그 및 HTML 엔티티 제거."""
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", text)
    return html.unescape(cleaned).strip()


def build_search_queries(category: str, item: dict[str, Any]) -> list[str]:
    """
    pc-builder-parts의 영문 vendor/model에서 다나와 검색 친화적인 쿼리 후보 리스트 생성.
    1순위 쿼리 실패 시 2순위(연도/괄호 제거 등) 쿼리로 폴백.
    """
    vendor = item.get("vendor", "").strip()
    model = item.get("model", "").strip()

    # "NVIDIA AIB", "AMD AIB" 같은 가상 벤더명은 검색어에서 제외
    clean_vendor = "" if "AIB" in vendor.upper() else vendor

    # 괄호 안 연도나 파트넘버 제거 버전: 예) "H7 Flow (2024)" -> "H7 Flow"
    model_no_paren = re.sub(r"\s*\([^)]*\)", "", model).strip()
    # RAM 등에서 "32GB (2x16GB)" 같은 세부 표기 단순화
    model_compact = re.sub(r"\s+", " ", model_no_paren)

    queries: list[str] = []

    if category == "cpu":
        # 예: "Ryzen 5 9600X" -> "9600X", "Core Ultra 7 265K" -> "265K"
        tokens = model_no_paren.split()
        core_code = tokens[-1] if tokens else model_no_paren
        queries.append(f"{clean_vendor} {core_code}".strip())
        queries.append(core_code)
    elif category == "gpu":
        # 예: "RTX 5060 Ti 16GB"
        queries.append(model_no_paren)
    elif category == "ram":
        # 예: "G.Skill Trident Z5 Neo 32GB (2x16GB) DDR5-6000 CL30"
        # 다나와는 "G.Skill DDR5-6000 CL30 Trident Z5 Neo 32GB" 형태가 잘 걸림
        queries.append(f"{clean_vendor} {model_no_paren}".strip())
        # 조금 더 짧은 키워드
        short_ram = re.sub(r"\b\d+x\d+GB\b", "", model_no_paren).strip()
        if short_ram != model_no_paren:
            queries.append(f"{clean_vendor} {short_ram}".strip())
    elif category == "psu":
        # 예: "Corsair RM750x (2024) 750W 80+ Gold" -> "Corsair RM750x" 도 폴백으로 추가
        queries.append(f"{clean_vendor} {model_no_paren}".strip())
        first_token = model_no_paren.split()[0] if model_no_paren else ""
        if first_token:
            queries.append(f"{clean_vendor} {first_token}".strip())
    else:
        queries.append(f"{clean_vendor} {model}".strip())
        if model_no_paren != model:
            queries.append(f"{clean_vendor} {model_no_paren}".strip())

    # 중복 제거 (순서 유지)
    deduped: list[str] = []
    for q in queries:
        if q and q not in deduped:
            deduped.append(q)
    return deduped


def score_candidate(
    category: str,
    part_item: dict[str, Any],
    danawa_item: dict[str, Any],
) -> float:
    """
    다나와 검색 결과 아이템이 해당 PC 부품에 적합한지 점수 부여.
    부적합(해외구매, 중고, 완제품 PC 등)은 음수 반환.
    """
    name = strip_html(danawa_item.get("productName", ""))
    name_upper = name.upper()
    cat_code = str(danawa_item.get("category") or "")
    price = danawa_item.get("minPrice")

    if not price or not isinstance(price, (int, float)) or price <= 0:
        return -999.0

    # 해외구매, 중고, 리퍼, 벌크(CPU 제외), 빈박스 등 제외
    if any(bad in name for bad in ("해외구매", "중고", "리퍼", "병행수입")):
        return -500.0

    score = 0.0

    # 1. 카테고리 prefix 일치 여부
    expected_prefixes = DANAWA_CATEGORY_PREFIX.get(category, ())
    if expected_prefixes:
        if cat_code.startswith(expected_prefixes):
            score += 50.0
        else:
            # 카테고리가 다르면 큰 감점 (예: CPU 검색했는데 조립PC나 메인보드가 나오는 경우)
            score -= 100.0

    # 2. 핵심 모델 토큰 포함 여부 확인
    model_no_paren = re.sub(r"\s*\([^)]*\)", "", part_item.get("model", "")).upper()
    tokens = [t for t in re.split(r"[\s\-/]+", model_no_paren) if len(t) >= 2]
    matched_tokens = sum(1 for t in tokens if t in name_upper)
    score += matched_tokens * 15.0

    # 3. CPU는 정품/멀티팩 선호, 리뷰 많은 상품 가산점
    if category == "cpu" and ("정품" in name or "멀티팩" in name):
        score += 10.0

    review_count = int(danawa_item.get("reviewCount") or 0)
    score += min(review_count, 100) * 0.1

    return score


def search_danawa(query: str, limit: int = 8) -> list[dict[str, Any]]:
    """npx danawa-cli search를 호출하여 결과 items 리스트 반환."""
    cmd = ["npx", "--yes", "danawa-cli", "search", query, "--limit", str(limit)]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            shell=(os.name == "nt"),
            timeout=25,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        payload = json.loads(proc.stdout)
        if not payload.get("ok"):
            return []
        return payload.get("items", [])
    except Exception:
        return []


def match_part_with_danawa(
    category: str,
    part_item: dict[str, Any],
    delay_range: tuple[float, float] = (0.4, 1.0),
) -> dict[str, Any]:
    """부품 1개에 대해 다나와 검색 후 최적 매칭 상품 반환."""
    queries = build_search_queries(category, part_item)

    best_candidate: dict[str, Any] | None = None
    best_score = -999.0
    used_query = queries[0] if queries else ""

    for q in queries:
        used_query = q
        items = search_danawa(q, limit=8)
        time.sleep(random.uniform(*delay_range))

        for item in items:
            sc = score_candidate(category, part_item, item)
            if sc > best_score:
                best_score = sc
                best_candidate = item

        # 카테고리 일치 + 토큰 매칭이 충분히 된 경우 바로 채택
        if best_candidate and best_score >= 50.0:
            break

    if not best_candidate or best_score < 0:
        return {
            "danawa_pcode": None,
            "model_name_kr": None,
            "lowest_price_krw": None,
            "danawa_category": None,
            "danawa_url": None,
            "image_url": None,
            "review_count": None,
            "star_point": None,
            "is_available_kr": False,
            "search_query": used_query,
            "match_score": None,
        }

    pcode = str(best_candidate.get("productCode"))
    return {
        "danawa_pcode": pcode,
        "model_name_kr": strip_html(best_candidate.get("productName", "")),
        "lowest_price_krw": int(best_candidate["minPrice"]),
        "danawa_category": best_candidate.get("category"),
        "danawa_url": f"https://prod.danawa.com/info/?pcode={pcode}",
        "image_url": best_candidate.get("imageUrl"),
        "review_count": best_candidate.get("reviewCount"),
        "star_point": best_candidate.get("starPoint"),
        "is_available_kr": True,
        "search_query": used_query,
        "match_score": round(best_score, 1),
    }


def fetch_pc_builder_parts(raw_path: Path) -> dict[str, Any]:
    """GitHub에서 최신 pc-builder-parts.json 다운로드 및 로컬 저장."""
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        PC_BUILDER_PARTS_URL,
        headers={"User-Agent": "SKN35-BUILDWISE-CatalogSync/1.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        content = resp.read().decode("utf-8")
    raw_path.write_text(content, encoding="utf-8")
    return json.loads(content)


def save_to_sqlite(
    db_path: Path,
    catalog_rows: list[dict[str, Any]],
    meta: dict[str, Any],
    performance_tiers: dict[str, Any],
) -> None:
    """통합 카탈로그와 메타/호환성 규칙을 SQLite 테이블로 저장."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS parts_catalog (
            part_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            vendor TEXT NOT NULL,
            model_name_en TEXT NOT NULL,
            performance_tier TEXT,
            danawa_pcode TEXT,
            model_name_kr TEXT,
            lowest_price_krw INTEGER,
            is_available_kr INTEGER NOT NULL,
            danawa_url TEXT,
            image_url TEXT,
            review_count INTEGER,
            star_point TEXT,
            search_query TEXT,
            match_score REAL,
            specs_json TEXT NOT NULL,
            use_cases_json TEXT,
            notes TEXT,
            spec_last_verified TEXT,
            price_updated_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS catalog_metadata (
            meta_key TEXT PRIMARY KEY,
            meta_value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    for row in catalog_rows:
        cur.execute(
            """
            INSERT INTO parts_catalog (
                part_id, category, vendor, model_name_en, performance_tier,
                danawa_pcode, model_name_kr, lowest_price_krw, is_available_kr,
                danawa_url, image_url, review_count, star_point,
                search_query, match_score, specs_json, use_cases_json,
                notes, spec_last_verified, price_updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(part_id) DO UPDATE SET
                category=excluded.category,
                vendor=excluded.vendor,
                model_name_en=excluded.model_name_en,
                performance_tier=excluded.performance_tier,
                danawa_pcode=excluded.danawa_pcode,
                model_name_kr=excluded.model_name_kr,
                lowest_price_krw=excluded.lowest_price_krw,
                is_available_kr=excluded.is_available_kr,
                danawa_url=excluded.danawa_url,
                image_url=excluded.image_url,
                review_count=excluded.review_count,
                star_point=excluded.star_point,
                search_query=excluded.search_query,
                match_score=excluded.match_score,
                specs_json=excluded.specs_json,
                use_cases_json=excluded.use_cases_json,
                notes=excluded.notes,
                spec_last_verified=excluded.spec_last_verified,
                price_updated_at=excluded.price_updated_at
            """,
            (
                row["part_id"],
                row["category"],
                row["vendor"],
                row["model_name_en"],
                row["performance_tier"],
                row["danawa_pcode"],
                row["model_name_kr"],
                row["lowest_price_krw"],
                1 if row["is_available_kr"] else 0,
                row["danawa_url"],
                row["image_url"],
                row["review_count"],
                row["star_point"],
                row["search_query"],
                row["match_score"],
                json.dumps(row["specs"], ensure_ascii=False),
                json.dumps(row["use_cases"], ensure_ascii=False),
                row["notes"],
                row["spec_last_verified"],
                row["price_updated_at"],
            ),
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        INSERT INTO catalog_metadata (meta_key, meta_value_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(meta_key) DO UPDATE SET
            meta_value_json=excluded.meta_value_json,
            updated_at=excluded.updated_at
        """,
        ("_meta", json.dumps(meta, ensure_ascii=False), now_iso),
    )
    cur.execute(
        """
        INSERT INTO catalog_metadata (meta_key, meta_value_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(meta_key) DO UPDATE SET
            meta_value_json=excluded.meta_value_json,
            updated_at=excluded.updated_at
        """,
        ("performance_tiers", json.dumps(performance_tiers, ensure_ascii=False), now_iso),
    )

    conn.commit()
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync pc-builder-parts with danawa-cli prices")
    parser.add_argument(
        "--sample-per-category",
        type=int,
        default=2,
        help="카테고리별 샘플링할 부품 개수 (전체 실행 시 --all 사용)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="전체 부품(126개) 모두 동기화",
    )
    args = parser.parse_args()

    raw_json_path = RAW_DIR / "pc-builder-parts.json"
    print(f"[1/4] GitHub에서 최신 pc-builder-parts 데이터셋 다운로드 중... -> {raw_json_path}")
    dataset = fetch_pc_builder_parts(raw_json_path)

    meta = dataset.get("_meta", {})
    performance_tiers = dataset.get("performance_tiers", {})

    catalog_rows: list[dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("[2/4] danawa-cli 연동하여 한국 다나와 최저가(KRW) 및 상품코드 매칭 중...")
    for category in CATEGORIES:
        items = dataset.get(category, [])
        target_items = items if args.all else items[: args.sample_per_category]

        for item in target_items:
            part_id = item["id"]
            vendor = item.get("vendor", "")
            model_en = item.get("model", "")

            # 공통 필드 제외한 나머지 기술 스펙을 specs 딕셔너리로 분리
            excluded_keys = {
                "id",
                "vendor",
                "model",
                "performance_tier",
                "use_cases",
                "notes",
                "last_verified",
            }
            specs = {k: v for k, v in item.items() if k not in excluded_keys}

            danawa_info = match_part_with_danawa(category, item)

            row = {
                "part_id": part_id,
                "category": category,
                "vendor": vendor,
                "model_name_en": model_en,
                "performance_tier": item.get("performance_tier"),
                "danawa_pcode": danawa_info["danawa_pcode"],
                "model_name_kr": danawa_info["model_name_kr"],
                "lowest_price_krw": danawa_info["lowest_price_krw"],
                "is_available_kr": danawa_info["is_available_kr"],
                "danawa_url": danawa_info["danawa_url"],
                "image_url": danawa_info["image_url"],
                "review_count": danawa_info["review_count"],
                "star_point": danawa_info["star_point"],
                "search_query": danawa_info["search_query"],
                "match_score": danawa_info["match_score"],
                "specs": specs,
                "use_cases": item.get("use_cases", []),
                "notes": item.get("notes"),
                "spec_last_verified": item.get("last_verified"),
                "price_updated_at": now_iso,
            }
            catalog_rows.append(row)

            price_str = (
                f"{row['lowest_price_krw']:,}원"
                if row["lowest_price_krw"] is not None
                else "미확인(null)"
            )
            print(
                f"  - [{category.upper()}] {vendor} {model_en} "
                f"=> {row['model_name_kr'] or '매칭 실패'} | {price_str} (pcode={row['danawa_pcode']})"
            )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_json = PROCESSED_DIR / "parts_catalog.json"
    out_csv = PROCESSED_DIR / "parts_catalog.csv"
    out_db = PROCESSED_DIR / "parts_catalog.db"

    print(f"[3/4] JSON 및 CSV 파일 저장 중... -> {out_json}, {out_csv}")
    out_json.write_text(
        json.dumps(
            {
                "_meta": meta,
                "synced_at": now_iso,
                "total_synced": len(catalog_rows),
                "available_kr_count": sum(1 for r in catalog_rows if r["is_available_kr"]),
                "items": catalog_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    csv_fields = [
        "part_id",
        "category",
        "vendor",
        "model_name_en",
        "performance_tier",
        "danawa_pcode",
        "model_name_kr",
        "lowest_price_krw",
        "is_available_kr",
        "danawa_url",
        "review_count",
        "star_point",
        "specs_summary",
        "price_updated_at",
    ]
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in catalog_rows:
            writer.writerow(
                {
                    "part_id": r["part_id"],
                    "category": r["category"],
                    "vendor": r["vendor"],
                    "model_name_en": r["model_name_en"],
                    "performance_tier": r["performance_tier"],
                    "danawa_pcode": r["danawa_pcode"],
                    "model_name_kr": r["model_name_kr"],
                    "lowest_price_krw": r["lowest_price_krw"],
                    "is_available_kr": r["is_available_kr"],
                    "danawa_url": r["danawa_url"],
                    "review_count": r["review_count"],
                    "star_point": r["star_point"],
                    "specs_summary": json.dumps(r["specs"], ensure_ascii=False),
                    "price_updated_at": r["price_updated_at"],
                }
            )

    print(f"[4/4] SQLite DB 테이블(parts_catalog) 업데이트 중... -> {out_db}")
    save_to_sqlite(out_db, catalog_rows, meta, performance_tiers)
    print(
        f"\n완료! 총 {len(catalog_rows)}개 부품 중 "
        f"{sum(1 for r in catalog_rows if r['is_available_kr'])}개 한국 다나와 가격 매칭 성공."
    )


if __name__ == "__main__":
    main()
