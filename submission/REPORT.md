# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:**Bùi Thị Thu Uyên
- **MSSV:**2A202602613
- **Lớp:** K4-L3A
- **Repository URL:**https://github.com/Ujandok/K4-L3A-Day13-BuiThiThuUyen-02613-Monitoring-LLMOps.git
- **Commit SHA cuối:**
- **Challenge ID:**
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-02613`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Baseline: 20/21 record có `correlation_id=MISSING` và thiếu enrichment. Sau CP1: middleware sinh/nhận `x-request-id`, bind context trước `request_received`, scrub PII trước khi render/ghi file |
| `validate_dashboard.py` | 6/6 | 6/6 | Contract có sẵn trong `config/dashboard.yaml`; validator chỉ kiểm tra cấu trúc, dashboard runtime xem `evidence/11-dashboard-overview.png` |
| `pytest` | Lỗi collection 2 file test | 28 passed | Baseline chạy nhầm Python của Anaconda (ngoài `.venv`) nên thiếu `structlog`, `langfuse`. Đã activate `.venv` và thêm test PII (CCCD, thẻ, passport) và middleware |
| Số traces hợp lệ | 0 | <số trace> | Baseline chỉ có root observation `lab-agent-run`, chưa có child retrieval/generation nên chưa đạt yêu cầu waterfall |
| Số PII leak | 0 | 0 | Baseline đã 0 vì `summarize_text()` gọi `scrub_text()` cho preview; nhưng chưa có processor scrub toàn bộ event trước khi ghi file. Sau CP1 scrub đệ quy mọi field, thêm CCCD/passport |
| Latency P95 / TTFT P95 | 1466 ms / 50 ms | 5758 ms / 50 ms (tạm, đo sau CP1) | Mẫu nhỏ (~10–13 request) nên P95 ≈ max, bị 1 request outlier chi phối. TTFT ổn định 50 ms (FakeLLM sleep cố định) → phần chậm nằm ngoài LLM; nghi bước fetch prompt Langfuse (cache TTL 60s, timeout 2s) nằm trong `latency_ms`. Sẽ kiểm chứng bằng waterfall ở CP2 và đo lại trên workload sạch |
| Retrieval success rate | 100% (10/10) | <sau CP2/CP3> | Không có `request_failed` trong baseline |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
- **Các metadata được ghi vào structured log:**
- **Cách bảo đảm PII được scrub trước khi ghi:**
- **Cách kiểm chứng kết quả:**

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
- **Cấu trúc root/retrieval/generation observations:**
- **Cách nối trace với log:**
- **Prompt name:**
- **Version/label baseline:**
- **Version/label candidate:**
- **Trace ID của mỗi version:**
- **Cách promote và rollback `production`:**

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
- **SLO và lý do chọn:**
- **Cách tính error budget:**
- **Ba alert và runbook tương ứng:**

## 7. Điều tra challenge

- **Challenge ID:**
- **Khoảng thời gian điều tra:**
- **Triệu chứng từ metrics:**
- **Log line và correlation ID liên quan:**
- **Trace ID và span gây ảnh hưởng:**
- **Root cause:**
- **Fix action:**
- **Preventive measure:**

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
- **Một lỗi/blocker đã gặp:**
- **Cách tìm nguyên nhân và xử lý:**
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
