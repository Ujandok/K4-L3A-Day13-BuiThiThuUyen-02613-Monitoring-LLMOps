# Alert và Runbook

Mỗi alert dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ. Điều tra luôn theo thứ tự **Metrics → Logs → Traces**.

Lệnh lọc log dùng chung (chạy từ thư mục gốc repo, Windows/macOS/Linux đều được):

```bash
python -c "import json;[print(r['ts'],r['correlation_id'],r.get('latency_ms'),r.get('error_type'),r.get('cost_usd')) for r in map(json.loads,open('data/logs.jsonl',encoding='utf-8')) if r.get('event') in ('response_sent','request_failed')]"
```

## Alert 1

- Tên: `chat_latency_p95_high`
- Severity: high
- Duration: 5m
- Kênh thông báo: Slack `#day13-k4-l3a-alerts`
- SLI/SLO liên quan: `fast_successful_requests` — 99.5% request thành công với `latency_ms <= 2000` trong 28 ngày
- Điều kiện và thời gian duy trì: P95 `latency_ms` của `response_sent` > 2000 ms liên tục 5 phút
- Ảnh hưởng tới người dùng: câu trả lời chậm rõ rệt; error budget của SLO bị tiêu nhanh
- Ba bước kiểm tra đầu tiên:
  1. Dashboard panel Latency: P95/P99 tăng từ lúc nào, TTFT P95 có tăng theo không (TTFT không đổi mà latency tăng → chậm nằm ngoài bước sinh token đầu).
  2. Lọc log `response_sent` có `latency_ms > 2000`, lấy vài `correlation_id`; kiểm tra có tập trung vào một `feature` không.
  3. Mở trace có cùng `correlation_id` trong Langfuse, so thời lượng span `retrieval` và `llm-generate` để biết bước nào chiếm thời gian.
- Mitigation tạm thời: nếu chậm ở retrieval → đặt timeout ngắn và trả lời bằng fallback không dùng context, bật cache kết quả retrieval; nếu chậm ở generation → giảm độ dài output hoặc chuyển model nhanh hơn.
- Owner: llm-app-oncall

## Alert 2

- Tên: `chat_error_rate_high`
- Severity: critical
- Duration: 5m
- Kênh thông báo: Slack `#day13-k4-l3a-alerts`
- SLI/SLO liên quan: `fast_successful_requests` (request lỗi là request xấu) và guardrail `error_rate_pct_max: 2`
- Điều kiện và thời gian duy trì: `request_failed / request_received × 100 > 2%` liên tục 5 phút
- Ảnh hưởng tới người dùng: người dùng nhận HTTP 500, không có câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Dashboard panel Errors: error rate, breakdown `error_type` và retrieval success rate có giảm cùng lúc không.
  2. Lọc log `request_failed`, xem `error_type`, `tool_name`, `tool_success` và `payload.detail`; lấy một `correlation_id`.
  3. Mở trace cùng `correlation_id`, tìm observation có level `ERROR` và đọc status message.
- Mitigation tạm thời: nếu lỗi từ dependency retrieval → bật fallback trả lời không dùng context hoặc circuit breaker để không gọi dependency đang hỏng; nếu lỗi xuất hiện ngay sau deploy/đổi prompt → rollback version trước.
- Owner: llm-app-oncall

## Alert 3

- Tên: `llm_cost_per_request_high`
- Severity: warning
- Duration: 15m
- Kênh thông báo: Slack `#day13-k4-l3a-alerts`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max: 2.5`
- Điều kiện và thời gian duy trì: trung bình `cost_usd` mỗi `response_sent` > 0.004 USD (≈ 2 lần baseline) liên tục 15 phút
- Ảnh hưởng tới người dùng: ngân sách bị đốt nhanh, có nguy cơ phải chặn dịch vụ; câu trả lời thường dài bất thường
- Ba bước kiểm tra đầu tiên:
  1. Dashboard panel Cost và Tokens: cost tăng trong khi Traffic không tăng? Tăng ở `tokens_in` hay `tokens_out`?
  2. Lọc log `response_sent` có `cost_usd` cao, so `tokens_in`/`tokens_out` với baseline, lấy `correlation_id`.
  3. Mở trace, xem usage/cost của generation `llm-generate` và `prompt_version`/`prompt_label` — prompt mới có làm output dài hơn không.
- Mitigation tạm thời: rollback label `production` về prompt version trước; giới hạn `max_tokens` cho output; nếu cần, rate-limit feature gây tốn kém.
- Owner: llm-app-oncall
