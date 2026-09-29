"""Tính số liệu cho bảng "Kết quả kỹ thuật" trong submission/REPORT.md.

Nguồn dữ liệu duy nhất là structured log (data/logs.jsonl) - cùng nguồn với dashboard.

Ví dụ:
    python scripts/report_stats.py                                  # log hiện tại
    python scripts/report_stats.py --log data/logs-baseline.jsonl   # số baseline
    python scripts/report_stats.py --last-minutes 15                # chỉ 15 phút gần nhất
    python scripts/report_stats.py --since "2026-09-29 16:40" --until "2026-09-29 17:00"
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.metrics import percentile  # dùng cùng công thức percentile với /metrics
from scripts.validate_logs import PII_DETECTORS  # dùng cùng detector với validator


def parse_log_ts(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_cli_time(value: str) -> datetime:
    # Giờ không có múi giờ được hiểu là giờ máy (Asia/Ho_Chi_Minh); log lưu UTC
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def load_records(path: Path, since: datetime | None, until: datetime | None) -> list[dict]:
    records: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            print(f"[bỏ qua] dòng {line_no} không phải JSON hợp lệ")
            continue
        if since or until:
            ts = parse_log_ts(rec.get("ts", ""))
            if ts is None or (since and ts < since) or (until and ts > until):
                continue
        records.append(rec)
    return records


def numbers(records: list[dict], field: str) -> list:
    return [
        r[field]
        for r in records
        if isinstance(r.get(field), (int, float)) and not isinstance(r.get(field), bool)
    ]


def fmt(value: float | None, suffix: str = "", digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}{suffix}"


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Tính số liệu cho REPORT.md từ structured log")
    parser.add_argument("--log", type=Path, default=REPO_ROOT / "data" / "logs.jsonl")
    parser.add_argument("--since", help='Giờ máy, ví dụ "2026-09-29 16:40"')
    parser.add_argument("--until", help='Giờ máy, ví dụ "2026-09-29 17:00"')
    parser.add_argument("--last-minutes", type=int, help="Chỉ tính N phút gần nhất")
    parser.add_argument("--slow-ms", type=int, default=3000, help="Ngưỡng request chậm (mặc định 3000)")
    args = parser.parse_args()

    if not args.log.exists():
        print(f"Không tìm thấy {args.log}")
        return 1

    since = parse_cli_time(args.since) if args.since else None
    until = parse_cli_time(args.until) if args.until else None
    if args.last_minutes:
        since = datetime.now(timezone.utc) - timedelta(minutes=args.last_minutes)

    records = load_records(args.log, since, until)
    received = [r for r in records if r.get("event") == "request_received"]
    responses = [r for r in records if r.get("event") == "response_sent"]
    failed = [r for r in records if r.get("event") == "request_failed"]

    latencies = numbers(responses, "latency_ms")
    ttfts = numbers(responses, "ttft_ms")
    tool_results = [r["tool_success"] for r in records if isinstance(r.get("tool_success"), bool)]
    correlation_ids = {
        r["correlation_id"] for r in records if r.get("correlation_id") not in (None, "", "MISSING")
    }
    pii_types: Counter[str] = Counter()
    pii_records = 0
    for rec in records:
        raw = json.dumps(rec, ensure_ascii=False)
        hits = [name for name, detector in PII_DETECTORS.items() if detector.search(raw)]
        if hits:
            pii_records += 1
            pii_types.update(hits)

    p50 = percentile(latencies, 50) if latencies else None
    p95 = percentile(latencies, 95) if latencies else None
    p99 = percentile(latencies, 99) if latencies else None
    ttft_p95 = percentile(ttfts, 95) if ttfts else None
    error_rate = 100 * len(failed) / len(received) if received else None
    retrieval_rate = 100 * sum(tool_results) / len(tool_results) if tool_results else None
    quality = numbers(responses, "quality_score")
    cost_total = sum(numbers(responses, "cost_usd"))

    window = "toàn bộ file"
    if since or until:
        start = since.astimezone().strftime("%Y-%m-%d %H:%M") if since else "..."
        end = until.astimezone().strftime("%Y-%m-%d %H:%M") if until else "hiện tại"
        window = f"{start} → {end} (giờ máy)"

    print(f"=== Số liệu từ {args.log} | {window} ===")
    print(f"Log records               : {len(records)}")
    print(f"Unique correlation IDs    : {len(correlation_ids)}")
    print(f"Traffic (request_received): {len(received)}")
    print(f"Thành công / lỗi          : {len(responses)} / {len(failed)}")
    print(f"Error rate                : {fmt(error_rate, '%')}")
    if failed:
        breakdown = Counter(r.get("error_type") or "unknown" for r in failed)
        print(f"Error breakdown           : {dict(breakdown)}")
    print(f"Latency P50/P95/P99       : {fmt(p50)} / {fmt(p95)} / {fmt(p99)} ms")
    print(f"TTFT P95                  : {fmt(ttft_p95)} ms")
    print(
        f"Retrieval success rate    : {fmt(retrieval_rate, '%')}"
        f" ({sum(tool_results)}/{len(tool_results)})"
    )
    print(f"Tokens in / out           : {sum(numbers(responses, 'tokens_in'))} / {sum(numbers(responses, 'tokens_out'))}")
    print(f"Cost tổng                 : {cost_total:.6f} USD")
    print(f"Quality trung bình        : {fmt(mean(quality) if quality else None, digits=3)}")
    print(f"PII leak (record)         : {pii_records} {dict(pii_types) if pii_types else ''}")

    slow = sorted(
        (r for r in responses if isinstance(r.get("latency_ms"), (int, float)) and r["latency_ms"] > args.slow_ms),
        key=lambda r: r["latency_ms"],
        reverse=True,
    )
    print(f"\nRequest chậm > {args.slow_ms} ms: {len(slow)}")
    for r in slow[:5]:
        print(f"  {r.get('ts')} | {r.get('correlation_id')} | {r.get('feature')} | {r['latency_ms']} ms")
    for r in failed[:5]:
        print(f"  [lỗi] {r.get('ts')} | {r.get('correlation_id')} | {r.get('error_type')}")

    print("\n=== Giá trị để dán vào bảng REPORT.md ===")
    print(f"Số PII leak              : {pii_records}")
    print(f"Latency P95 / TTFT P95   : {fmt(p95, ' ms', 0)} / {fmt(ttft_p95, ' ms', 0)}")
    print(
        f"Retrieval success rate   : {fmt(retrieval_rate, '%')}"
        f" ({sum(tool_results)}/{len(tool_results)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
