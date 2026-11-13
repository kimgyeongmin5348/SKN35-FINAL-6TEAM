"""Bounded public-source collection. This command never writes to MySQL."""

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from urllib.request import Request, urlopen

from app.domains.hardware.ingestion.common import (
    DATA,
    read_json,
    report,
    run_cli,
    stamp,
    utc_now,
    write_json,
)
from app.domains.hardware.ingestion.paths import TOOLS
from app.domains.hardware.ingestion.price_page import parse_component_price_page

CATALOG_URL = (
    "https://raw.githubusercontent.com/iBlessi/pc-builder-parts/main/pc-builder-parts.json"
)


def collect_price_page(match, run_dir):
    code = match.get("danawa_product_code")
    if not code or not match.get("expected_listing_name") or not match["import_enabled"]:
        return None
    url = f"https://prod.danawa.com/info/?pcode={code}"
    try:
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as response:
            body = response.read(3_000_001)
        if len(body) > 3_000_000:
            return {"verified": False, "reason": "PAGE_TOO_LARGE"}
        path = DATA / "raw/danawa" / run_dir / f"{code}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        evidence = parse_component_price_page(body.decode("utf-8", errors="replace"), match)
        return {
            **evidence,
            "source_url": url,
            "checked_at_utc": utc_now(),
            "path": path.relative_to(DATA).as_posix(),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
    except (OSError, ValueError) as error:
        return {"verified": False, "reason": type(error).__name__}


def collect_catalog(run_dir):
    request = Request(CATALOG_URL, headers={"User-Agent": "PC-Catalog-Pilot/1.0"})
    with urlopen(request, timeout=25) as response:
        content = response.read(5_000_001)
    if len(content) > 5_000_000:
        raise ValueError("부품 원본의 크기가 예상 범위를 벗어났습니다.")
    payload = json.loads(content)
    if not isinstance(payload.get("cpu"), list) or not isinstance(payload.get("_meta"), dict):
        raise ValueError("부품 원본 형식이 변경됐습니다.")
    target = DATA / "raw" / "pc_builder" / run_dir / "pc-builder-parts.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return {
        "path": target.relative_to(DATA).as_posix(),
        "source_url": CATALOG_URL,
        "retrieved_at_utc": utc_now(),
        "sha256": hashlib.sha256(content).hexdigest(),
        "version": payload["_meta"].get("version"),
        "attribution": payload["_meta"].get("attribution_required"),
    }


def collect_danawa(matches, run_dir):
    executable = shutil.which("node")
    cli = TOOLS / "node_modules" / "danawa-cli" / "bin" / "danawa.mjs"
    if not executable or not cli.exists():
        raise ValueError(
            "Node.js와 scripts/data/tools의 danawa-cli를 설치하세요. docs/database/README.md 참고."
        )
    installed = read_json(cli.parents[1] / "package.json")["version"]
    if installed != "3.0.0":
        raise ValueError("검토한 danawa-cli 버전은 3.0.0입니다.")
    records = []
    for match in matches:
        query = match["query"]
        started = utc_now()
        try:
            result = subprocess.run(
                [executable, str(cli), "search", query, "--limit", "20"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=40,
                shell=False,
            )
            payload = json.loads(result.stdout) if result.stdout.strip() else None
            record = {
                "source_key": match["source_key"],
                "query": query,
                "queried_at_utc": started,
                "cli_version": installed,
                "exit_code": result.returncode,
                "response": payload,
            }
            # Only fetch the specifically reviewed product, never a search hit chosen by similarity.
            if (
                payload
                and payload.get("ok")
                and any(
                    str(item.get("productCode")) == match.get("danawa_product_code")
                    for item in payload.get("items", [])
                )
            ):
                record["price_evidence"] = collect_price_page(match, run_dir)
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
            record = {
                "source_key": match["source_key"],
                "query": query,
                "queried_at_utc": started,
                "cli_version": installed,
                "response": None,
                "error_type": type(error).__name__,
            }
        path = DATA / "raw" / "danawa" / run_dir / (match["source_key"] + ".json")
        write_json(path, record)
        ok = bool((record.get("response") or {}).get("ok"))
        records.append(
            {"source_key": match["source_key"], "path": path.relative_to(DATA).as_posix(), "ok": ok}
        )
        print(f"수집: {match['source_key']} / {'성공' if ok else '보류'}", flush=True)
        time.sleep(0.3)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["catalog", "danawa", "all"], default="all")
    parser.add_argument("--only", help="part_matches.json의 source_key 하나만 수집")
    args = parser.parse_args()
    rows = read_json(DATA / "part_matches.json")["parts"]
    if args.only:
        rows = [row for row in rows if row["source_key"] == args.only]
        if not rows:
            raise ValueError("알 수 없는 source_key입니다.")
    manifest_path = DATA / "raw" / "collection_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    run_dir = stamp()
    if args.source in ("catalog", "all"):
        manifest["catalog"] = collect_catalog(run_dir)
    if args.source in ("danawa", "all"):
        records = collect_danawa(rows, run_dir)
        index = {item["source_key"]: item for item in manifest.get("danawa", [])}
        index.update({item["source_key"]: item for item in records})
        manifest["danawa"] = list(index.values())
    manifest["collected_at_utc"] = utc_now()
    write_json(manifest_path, manifest)
    # Keep the run manifest as well as the latest pointer, including failures.
    write_json(DATA / "raw" / "manifests" / (run_dir + ".json"), manifest)
    failed = [r["source_key"] for r in manifest.get("danawa", []) if not r["ok"]]
    report("collection", {"catalog": manifest.get("catalog"), "failed_queries": failed})
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
