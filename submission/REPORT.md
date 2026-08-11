# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: Cường Độ Đức Trí
- Repository URL: https://github.com/lecuong1502/Day13-K3-Observabilit-CuongDoDucTri
- Commit SHA cuối: _(điền sau khi commit — chạy `git rev-parse HEAD`)_
- Thành viên và vai trò:
  - Lê Kiên Cường — Metrics & Alerting
  - Xuân Thế Độ — Security & Compliance
  - Trần Công Đức — Logging & Middleware
  - Nguyễn Công Trí — QA & Incident Analyst

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: 30/100 (baseline CP0) → 100/100 (sau CP1)
- Tổng số traces: 10 trace runs (tương ứng 10 request qua `/chat`), mỗi trace gồm 3 observation lồng nhau (`run` → `retrieve` + `generate`) — tổng cộng 106 observations trên Langfuse trong 1 ngày gần nhất (bao gồm các lần chạy load test lặp lại)
- Số PII leak còn lại: 0 theo `validate_logs.py`; đã tự kiểm tra thủ công qua `grep "REDACTED" data/logs.jsonl`, xác nhận email/phone/credit card được che đúng định dạng `[REDACTED_...]`
- Link/đường dẫn dashboard: dữ liệu lấy từ endpoint `http://localhost:8000/metrics`; contract 6 panel đã validate `HỢP LỆ: 6/6 panel` qua `python scripts/validate_dashboard.py`. Snapshot mẫu:
  - traffic: 10
  - latency_p50/p95/p99: 1486 / 1940 / 1940 ms
  - avg_cost_usd: 0.0019 | total_cost_usd: 0.019
  - tokens_in/out: 330 / 1199
  - error_rate_pct: 0.0
  - quality_avg: 0.88

## 3. Logging và tracing

- Evidence correlation ID: log có trường `correlation_id` dạng `req-<8hex>`, ví dụ `req-510167ed`, `req-1920bf0c`
- Evidence PII redaction: 3 dòng log mẫu đã che PII đúng định dạng `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CREDIT_CARD]` (lưu ảnh trong `submission/evidence/`)
- Evidence trace waterfall: ảnh chụp Tracing trên Langfuse Cloud (project Day13-K3), thấy rõ cấu trúc `run` (span cha) → `retrieve` (span RAG) + `generate` (span LLM, type GENERATION) lồng bên trong, mỗi trace có Start Time, Input, Output, Metadata riêng
- Giải thích một span đáng chú ý: Span `generate` (type GENERATION) mang thông tin quan trọng nhất cho việc điều tra sự cố — chứa `usage_details` (prompt_tokens/completion_tokens), `cost_details`, và metadata `prompt_version`/`prompt_label`. Khi kết hợp với `correlation_id` được gắn vào metadata của generation, ta có thể truy ngược từ một dòng log lỗi trong `data/logs.jsonl` sang đúng trace/span tương ứng trên Langfuse để xem input/output đầy đủ và thời gian xử lý — đây là mắt xích nối giữa Metrics (phát hiện bất thường) → Traces (khoanh vùng) → Logs (xác nhận root cause).

## 4. Prompt versioning

- Prompt name: _(chưa thực hiện)_
- Version/label baseline: _(chưa thực hiện)_
- Version/label candidate: _(chưa thực hiện)_
- Trace ID của mỗi version: _(chưa thực hiện)_
- Bằng chứng đổi label hoặc rollback: _(chưa thực hiện)_

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: _(chưa chạy)_
- Evidence dashboard: _(chưa có)_
- SLO đã chọn và lý do: _(chưa thực hiện)_
- Alert rules và runbook: _(chưa thực hiện)_

## 6. Điều tra challenge

- Challenge ID: _(chờ Lab Coach release `config/challenge.json`)_
- Triệu chứng từ metrics: _(chưa thực hiện)_
- Trace ID liên quan: _(chưa thực hiện)_
- Log line/correlation ID liên quan: _(chưa thực hiện)_
- Root cause: _(chưa thực hiện)_
- Fix action: _(chưa thực hiện)_
- Preventive measure: _(chưa thực hiện)_

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Lê Kiên Cường | Logging & PII (correlation ID middleware, structured logging, PII scrubbing) | _(điền link commit)_ | _(điền)_ |
| | | | |