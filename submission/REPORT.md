# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Bùi Thị Thu Uyên
- **MSSV:** 2A202602613
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/Ujandok/K4-L3A-Day13-BuiThiThuUyen-02613-Monitoring-LLMOps
- **Commit SHA cuối:** 
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-02613`

## 2. Evidence index

| Evidence | Đường dẫn |
|---|---|
| Baseline trước khi sửa | [`evidence/00-baseline.txt`](evidence/00-baseline.txt) |
| Pytest cuối | [`evidence/01-pytest.png`](evidence/01-pytest.png) |
| Log validator | [`evidence/02-log-validator.png`](evidence/02-log-validator.png) |
| Dashboard validator | [`evidence/03-dashboard-validator.png`](evidence/03-dashboard-validator.png) |
| Structured log | [`evidence/04a-structured-log.png`](evidence/04a-structured-log.png), [`04b`](evidence/04b-structured-log.png), [`04c`](evidence/04c-structured-log.png) |
| PII redaction | [`evidence/05-pii-redaction.png`](evidence/05-pii-redaction.png) |
| Trace list | [`evidence/06-trace-list.png`](evidence/06-trace-list.png) |
| Trace waterfall | [`evidence/07-trace-waterfall.png`](evidence/07-trace-waterfall.png) |
| Trace metadata | [`evidence/08a-trace-metadata.png`](evidence/08a-trace-metadata.png), [`08b-trace-generation`](evidence/08b-trace-generation.png) |
| Prompt versions | [`evidence/09-prompt-versions.png`](evidence/09-prompt-versions.png) |
| Prompt rollback | [`10a-before`](evidence/10a-before.png), [`10b-promote`](evidence/10b-promote.png), [`10c-rollback`](evidence/10c-rollback.png) |
| Dashboard runtime | [`evidence/11-dashboard-overview.png`](evidence/11-dashboard-overview.png), [`11b-dashboard-rag-slow`](evidence/11b-dashboard-rag-slow.png) |
| Incident metric | [`evidence/12-incident-metric.png`](evidence/12-incident-metric.png) |
| Incident log | [`evidence/13-incident-log.png`](evidence/13-incident-log.png) |
| Incident trace | [`evidence/14-incident-trace.png`](evidence/14-incident-trace.png) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Baseline: 20/21 record có `correlation_id=MISSING` và thiếu enrichment. Sau CP1: middleware sinh/nhận `x-request-id`, bind context trước `request_received`, scrub PII trước khi render/ghi file |
| `validate_dashboard.py` | 6/6 | 6/6 | Contract có sẵn trong `config/dashboard.yaml`; validator chỉ kiểm tra cấu trúc, dashboard runtime xem `evidence/11-dashboard-overview.png` |
| `pytest` | Lỗi collection 2 file test | 28 passed | Baseline chạy nhầm Python của Anaconda (ngoài `.venv`) nên thiếu `structlog`, `langfuse`. Đã activate `.venv` và thêm test PII (CCCD, thẻ, passport) và middleware |
| Số traces hợp lệ | 0 | ⟨ĐIỀN: số trace trong Langfuse⟩ | Baseline chỉ có root observation `lab-agent-run`. Cuối: mỗi trace có root `lab-agent-run` + child `retrieval` (retriever) + `llm-generate` (generation có model, usage, cost) |
| Số PII leak | 0 | 0 | Baseline đã 0 vì `summarize_text()` gọi `scrub_text()` cho preview; nhưng chưa có processor scrub toàn bộ event trước khi ghi file. Sau CP1 scrub đệ quy mọi field, thêm CCCD/passport. Trace chỉ nhận input/output đã scrub |
| Latency P95 / TTFT P95 | 1466 ms / 50 ms | ⟨ĐIỀN⟩ ms / 50 ms (workload sạch ~50 request) | Lần đo đầu (~20 request) cho P95 = 4612 ms vì với mẫu nhỏ P95 ≈ max và bị 1 request outlier (request đầu tiên sau khởi động, ~4.6 s) chi phối. Đo lại trên ~50 request thì P95 phản ánh đúng mức bình thường; P99 vẫn chứa outlier. TTFT ổn định 50 ms |
| Retrieval success rate | 100% (10/10) | 100% | Dashboard 60 phút (gồm cả lúc chạy challenge) không có `request_failed`; error rate 0% |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` (`app/middleware.py`) gọi `clear_contextvars()` đầu mỗi request để không rò context từ request trước. Nếu client gửi header `x-request-id` thì dùng lại, nếu không thì sinh ID dạng `req-<8 ký tự hex>`. ID được `bind_contextvars(correlation_id=...)` nên mọi dòng log trong request tự có trường này, được lưu vào `request.state` để truyền sang agent/trace, và trả lại cho client qua header `x-request-id` cùng `x-response-time-ms`. Có test riêng trong `tests/test_middleware.py`.
- **Các metadata được ghi vào structured log:** Trong `app/main.py`, trước dòng `request_received` tôi bind `user_id_hash` (SHA-256 cắt 12 ký tự, không log user_id thô), `session_id`, `feature`, `model`, `env`. Dòng `response_sent` ghi thêm `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`; dòng `request_failed` ghi `error_type`. Đây chính là các field mà dashboard đọc.
- **Cách bảo đảm PII được scrub trước khi ghi:** Processor scrub được đăng ký trong `app/logging_config.py` **trước** `JsonlFileProcessor` và `JSONRenderer`, nên dữ liệu được làm sạch trước khi serialize hoặc ghi xuống `data/logs.jsonl`. Processor duyệt đệ quy mọi field chuỗi (không chỉ `payload`). `app/pii.py` có pattern cho email, số điện thoại Việt Nam, CCCD, thẻ thanh toán và passport.
- **Cách kiểm chứng kết quả:** `validate_logs.py` đạt 100/100 (0 PII leak), `tests/test_pii.py` kiểm tra từng loại PII, và `evidence/05-pii-redaction.png` cho thấy input mẫu chứa email/điện thoại/thẻ được thay bằng `[REDACTED_...]` trong log thực tế. Tôi không commit file log baseline (`data/logs-baseline.jsonl`) vì nó chứa PII chưa scrub; file đã được thêm vào `.gitignore`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Key trong `.env` thuộc project `day13-k4-l3a-02613`; `/health` trả `tracing_enabled: True`. Tôi tự chạy `scripts/load_test.py` và kiểm tra `correlation_id` trả về trong response trùng với metadata của trace mới nhất. Ảnh `06-trace-list.png` thấy tên project.
- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run` (type `agent`, `@observe`) có metadata `correlation_id`, `prompt_name`, `prompt_label`, `prompt_version`, `prompt_source`. Bên trong có hai child mở bằng `start_as_current_observation` của Langfuse SDK v4: `retrieval` (type `retriever`, input là query đã scrub, output `doc_count`, nếu lỗi thì gắn `level=ERROR` và status message) và `llm-generate` (type `generation`, có `model`, liên kết prompt, `usage_details` input/output/total, `cost_details` theo đơn giá $3/$15 mỗi 1M token). Raw prompt chứa PII không được gửi lên; chỉ gửi bản đã qua `summarize_text()`.
- **Cách nối trace với log:** Cùng một `correlation_id` xuất hiện trong mọi dòng log của request và trong trace metadata (qua `propagate_attributes`). Từ log lấy `req-...`, trên Langfuse tìm trace có metadata trùng.
- **Prompt name:** `day13-chat` (Text prompt, biến `{{feature}}`, `{{docs}}`, `{{message}}`).
- **Version/label baseline:** version 1 — labels `baseline`, `production` (ban đầu).
- **Version/label candidate:** version 2 — label `candidate`; thêm dòng `Answer in at most 3 sentences.`.
- **Trace ID của mỗi version:**
  - `baseline` (v1): trace `⟨ĐIỀN⟩`, correlation `⟨ĐIỀN⟩`
  - `candidate` (v2): trace `⟨ĐIỀN⟩`, correlation `⟨ĐIỀN⟩`
  - `production` sau promote (v2): trace `⟨ĐIỀN⟩`, correlation `⟨ĐIỀN⟩`
  - `production` sau rollback (v1): trace `⟨ĐIỀN⟩`, correlation `⟨ĐIỀN⟩`
- **Cách promote và rollback `production`:** App lấy prompt theo label (`LANGFUSE_PROMPT_LABEL`), không theo số version. Promote: gán label `production` cho version 2 bằng `langfuse.update_prompt(name="day13-chat", version=2, new_labels=["candidate","production"])`; Langfuse tự gỡ `production` khỏi version 1 vì label là duy nhất. Rollback: gán lại `production` cho version 1. Vì app cache prompt 60 giây, tôi restart API trước mỗi lần kiểm tra; trace metadata `prompt_version` đổi 1 → 2 → 1 mà không sửa code hay deploy lại (`evidence/10a`, `10b`, `10c`).

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dựng bằng Streamlit (`scripts/dashboard.py`, chạy `streamlit run scripts/dashboard.py`), đọc trực tiếp `data/logs.jsonl`. Time range, refresh, đơn vị và threshold được đọc từ `config/dashboard.yaml` nên luôn khớp contract: 60 phút, tự refresh 30 giây, mỗi panel có đường threshold đỏ nét đứt. Sáu panel: Latency P50/P95/P99 + TTFT P95; Traffic; Error rate + breakdown `error_type` + retrieval success; Cost theo phút và cộng dồn; Tokens in/out; Quality mean. Kiểm tra runtime: bật `rag_slow` thì P95 tăng rõ rệt (`evidence/11b-dashboard-rag-slow.png`).
- **SLO và lý do chọn:** 99.5% request thành công **và** có `latency_ms ≤ 2000` trong cửa sổ 28 ngày (`config/slo.yaml`). Tôi hạ ngưỡng từ 3000 ms xuống 2000 ms vì baseline sạch có P50 ≈ ⟨ĐIỀN⟩ ms, P95 ≈ ⟨ĐIỀN⟩ ms, nên 2000 ms vẫn còn nhiều headroom; còn với 3000 ms, một request có retrieval chậm thêm ~2.5 s (tổng ~2.7 s) vẫn bị tính là "tốt" và SLO không phát hiện được. Request lỗi tự động là request xấu vì có `request_received` nhưng không có `response_sent`. Threshold P95 3000 ms trên dashboard giữ nguyên theo contract.
- **Cách tính error budget:** Error budget = 100% − 99.5% = 0.5%. Với 10.000 request trong 28 ngày thì được phép tối đa 50 request chậm hoặc lỗi; quy ra thời gian là 0.5% × 28 × 24 h ≈ 3 giờ 22 phút. Khi budget bị tiêu nhanh (alert latency hoặc error bắn), cần ưu tiên ổn định hệ thống thay vì đẩy thay đổi mới (ví dụ prompt mới).
- **Ba alert và runbook tương ứng:** Trong `config/alert_rules.yaml`, runbook ở `docs/alerts.md`. Cả ba đều symptom-based (đo thứ người dùng hoặc ngân sách cảm nhận được), gửi Slack `#day13-k4-l3a-alerts`, owner `llm-app-oncall`:
  1. `chat_latency_p95_high` — P95 `latency_ms` > 2000 ms trong 5 phút, severity high.
  2. `chat_error_rate_high` — `request_failed / request_received` > 2% trong 5 phút, severity critical.
  3. `llm_cost_per_request_high` — cost trung bình mỗi request > ⟨ĐIỀN: ngưỡng, ≈ 2× baseline ⟨ĐIỀN⟩ USD⟩ trong 15 phút, severity warning.

  Mỗi runbook có ba bước kiểm tra theo thứ tự Metrics → Logs → Traces và mitigation tạm thời (fallback/timeout cho retrieval, circuit breaker, rollback label `production`, giới hạn output token).

## 7. Điều tra challenge

- **Challenge ID:** ⟨ĐIỀN⟩
- **Khoảng thời gian điều tra:** ⟨ĐIỀN: HH:MM–HH:MM⟩ giờ VN (⟨ĐIỀN⟩ UTC), ngày 29/9/2026
- **Triệu chứng từ metrics:** Panel Latency vượt ngưỡng: trong khoảng sự cố P95 ≈ ⟨ĐIỀN⟩ ms, P99 ≈ ⟨ĐIỀN⟩ ms (baseline P95 ≈ ⟨ĐIỀN⟩ ms), vượt threshold 3000 ms và ngưỡng alert 2000 ms. TTFT P95 giữ nguyên 50 ms; error rate 0%, retrieval success 100%, cost/tokens/quality trong ngưỡng. Kết luận ở tầng metric: sự cố là **chậm**, không phải lỗi hay chi phí, và phần chậm nằm ngoài bước sinh token đầu của LLM. (`evidence/12-incident-metric.png`)
- **Log line và correlation ID liên quan:** `⟨ĐIỀN: ts⟩ ⟨req-...⟩ feature=⟨...⟩ latency_ms=⟨...⟩` — lọc các `response_sent` sau dòng `incident_enabled`, request chậm tập trung ở feature ⟨ĐIỀN⟩. (`evidence/13-incident-log.png`)
- **Trace ID và span gây ảnh hưởng:** Trace `⟨ĐIỀN⟩`, metadata `correlation_id` trùng log. Span `retrieval` mất ≈ ⟨ĐIỀN⟩ ms, chiếm phần lớn tổng thời gian; `llm-generate` chỉ ≈ ⟨ĐIỀN⟩ ms như bình thường. (`evidence/14-incident-trace.png`)
- **Root cause:** Bước retrieval (tìm tài liệu cho RAG) phản hồi chậm khoảng 2.5 s mỗi request, làm tổng latency tăng. LLM không bị ảnh hưởng (TTFT và thời gian generation bình thường). Ba tầng cùng chỉ về một nguyên nhân: metric (latency tăng, TTFT không đổi) → log (request cụ thể chậm) → trace (span `retrieval` dài).
- **Fix action:** Khôi phục retrieval (tắt incident bằng `python scripts/inject_incident.py --disable`) rồi chạy lại load test để xác nhận latency quay về mức baseline ⟨ĐIỀN: số đo sau khi tắt, hoặc xóa câu này nếu không đo⟩. Nếu chưa khôi phục ngay được: đặt timeout ngắn cho retrieval và trả lời bằng fallback không dùng context.
- **Preventive measure:** Bật alert `chat_latency_p95_high` (P95 > 2000 ms trong 5 phút) để phát hiện sớm; thêm timeout + circuit breaker cho retrieval; cache kết quả retrieval cho câu hỏi lặp lại; theo dõi riêng thời lượng span `retrieval` để thấy xu hướng chậm dần trước khi vi phạm SLO.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Hạ ngưỡng SLO latency từ 3000 ms xuống 2000 ms. Khi thử `rag_slow`, tôi thấy latency khoảng 2.7 s vẫn dưới 3000 ms, tức SLO gốc không phát hiện được đúng loại sự cố mà dashboard thấy rõ. Ngưỡng 2000 ms vẫn cách xa baseline (P95 ≈ ⟨ĐIỀN⟩ ms) nên không gây báo động giả. Quyết định thứ hai: tách `retrieval` và `llm-generate` thành child observation qua một helper trong `app/tracing.py` thay vì gọi trực tiếp trên client được truyền vào agent, để giữ tương thích với test hiện có (test thay client bằng bản giả chỉ có `get_prompt`/`update_current_span`).
- **Một lỗi/blocker đã gặp:** Khi commit CP2, tôi vô tình `git add` cả `data/logs-baseline.jsonl` — file log trước CP1 còn email, số điện thoại và số thẻ chưa scrub. Cùng lúc `git push` thất bại với HTTP 408 do mạng upload chậm.
- **Cách tìm nguyên nhân và xử lý:** Rà danh sách file trong output `git commit` thì thấy file log. Vì push chưa thành công nên commit chưa lên remote: tôi `git rm --cached data/logs-baseline.jsonl`, thêm `data/logs-*.jsonl` vào `.gitignore`, rồi `git commit --amend` để commit không còn chứa PII. Cùng lúc chuyển runbook từ `config/alerts.md` về đúng `docs/alerts.md` và sửa tên ảnh bị lặp đuôi. Lỗi 408 xử lý bằng cách tăng `http.postBuffer` ⟨ĐIỀN: và/hoặc đổi mạng — ghi đúng cách bạn đã làm⟩. Bài học: luôn đọc `git status` trước khi commit, và đưa mọi file log vào `.gitignore` ngay từ đầu.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics trả lời "có vấn đề gì và từ khi nào" nhưng là số tổng hợp, không chỉ ra request nào. Logs trả lời "request nào bị ảnh hưởng": lọc trong khoảng thời gian đó để lấy `correlation_id` cụ thể. Traces trả lời "bước nào gây ra": mở trace cùng `correlation_id` và so thời lượng/trạng thái từng span. Trong challenge: metric cho thấy P95 tăng nhưng TTFT không đổi → log chỉ ra request `⟨req-...⟩` chậm → trace cho thấy span `retrieval` chiếm phần lớn thời gian. Chỉ kết luận khi cả ba tầng cùng chỉ về một nguyên nhân.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt là một phần "code" của ứng dụng LLM nhưng thay đổi thường xuyên hơn; gắn `prompt_version` vào trace giúp biết chính xác request nào dùng prompt nào khi chất lượng hoặc chi phí thay đổi. Label cho phép promote/rollback tức thì mà không deploy lại. Token/cost cần theo dõi riêng vì chi phí LLM tăng theo output token, có thể tăng mạnh mà traffic không đổi (prompt mới làm câu trả lời dài hơn). SLO và error budget giúp quyết định khi nào được thử thay đổi mới và khi nào phải ưu tiên ổn định hoặc rollback.
- **Điều quan trọng nhất đã học:** Chỉ số trung bình hay một con số percentile trên mẫu nhỏ rất dễ đánh lừa: với ~20 request, P95 gần như bằng request chậm nhất, nên một outlier khi khởi động đã đẩy P95 lên 4612 ms. Cần đủ dữ liệu, nhìn theo thời gian, và đi xuống log/trace trước khi kết luận.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** (1) Bước lấy prompt từ Langfuse nằm trong `latency_ms` nhưng chưa có span riêng, nên cold start chỉ thấy như một khoảng trống giữa hai span; nên thêm span `prompt-fetch` hoặc warm-up khi khởi động. (2) Metrics trong `/metrics` lưu trong bộ nhớ và mất khi restart. (3) Dashboard dùng cửa sổ 60 phút cố định nên số tổng trộn cả dữ liệu tập luyện và challenge; khi điều tra tôi đọc số theo từng phút trên biểu đồ. (4) Alert mới ở mức cấu hình, chưa nối vào Slack thật. (5) `chat` là `async` nhưng gọi agent đồng bộ, nên request chạy song song bị xếp hàng; `latency_ms` không phản ánh thời gian chờ này.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
