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

- Challenge ID: day13-k3-observability-v1
- Triệu chứng từ metrics: `latency_p95` tăng vọt lên 4292ms, `latency_p50` = 4054ms — vượt xa `latency_threshold_ms: 2000` quy định trong challenge (gấp hơn 2 lần ngưỡng). `error_rate_pct` vẫn 0% — đây không phải lỗi hệ thống mà là vấn đề hiệu năng.

- Trace ID liên quan: trace có `correlation_id = req-ac019214` (latency 4292ms — trùng khớp chính xác với `latency_p95` trong `/metrics`), session `k3-challenge-s04`. Trên Langfuse, waterfall của trace này cho thấy span `retrieve` chiếm phần lớn thời gian xử lý (~2.5s), phần còn lại là `generate` (~0.15s) cộng overhead.

- Log line/correlation ID liên quan:
```json
{"service": "api", "payload": {"message_preview": "Can a customer request a refund after purchase?"}, "event": "request_received", "session_id": "k3-challenge-s04", "feature": "refund", "correlation_id": "req-ac019214", "ts": "2026-08-11T04:12:47.009582Z"}
{"service": "api", "latency_ms": 4292, "event": "response_sent", "session_id": "k3-challenge-s04", "feature": "refund", "correlation_id": "req-ac019214", "ts": "2026-08-11T04:12:51.303657Z"}
```
Đối chiếu thêm log `incident_enabled`:
```json
{"service": "control", "payload": {"name": "rag_slow"}, "event": "incident_enabled", "ts": "2026-08-11T04:12:38.814981Z"}
```
xác nhận incident `rag_slow` được bật đúng 4.1 giây trước khi request đầu tiên của challenge tới.

- Root cause: Có 2 nguyên nhân cộng hưởng:
  1. **Nguyên nhân chính (theo thiết kế incident)**: `rag_slow` được kích hoạt khiến hàm `retrieve()` trong `app/mock_rag.py` thêm `time.sleep(2.5)`, chỉ ảnh hưởng feature `refund` vì corpus tra cứu của incident này match đúng từ khóa "refund" trong `CORPUS`. Điều này cộng với baseline xử lý (~1.4-1.7s) tạo ra latency ~3.9-4.3s mỗi request.
  2. **Nguyên nhân phụ (vấn đề kiến trúc)**: Dựa vào timestamp log, 5 request được gửi với `--concurrency 5` nhưng bị xử lý **tuần tự hoàn toàn** — response của request N kết thúc chỉ 2ms trước khi request N+1 bắt đầu, không có overlap. Nguyên nhân là do `chat()` trong `app/main.py` là `async def` nhưng gọi `agent.run()` (hàm đồng bộ, chứa `time.sleep()` blocking) trực tiếp không qua `await` hay `run_in_executor` — khiến toàn bộ event loop bị chặn (block) trong lúc xử lý từng request, biến 5 request "song song" thành hàng đợi nối tiếp. Đây là lý do request cuối cùng trong batch client-side đo được latency lên tới ~20s dù server-side mỗi request riêng lẻ chỉ mất ~4s.

- Fix action:
  - Ngắn hạn (khắc phục sự cố `rag_slow`): tắt incident ngay khi phát hiện (`python scripts/inject_incident.py --disable`), đồng thời với hệ thống production thật sẽ cần kiểm tra vector store/RAG backend có đang gặp sự cố thật (timeout, overload) hay không.
  - Dài hạn (khắc phục vấn đề kiến trúc phát hiện thêm): chuyển các lời gọi blocking (`agent.run()`, bên trong có `time.sleep`, retrieval, LLM call) sang chạy bất đồng bộ đúng cách — dùng `await asyncio.to_thread(agent.run, ...)` hoặc chuyển toàn bộ pipeline sang async I/O thật sự — để đảm bảo nhiều request có thể được xử lý song song, tránh hiệu ứng domino khi một request chậm làm nghẽn toàn bộ hàng đợi.

- Preventive measure:
  - Alert `high_latency_p95` (đã cấu hình ở CP2, ngưỡng 3000ms/5 phút) sẽ tự động cảnh báo on-call ngay khi P95 vượt ngưỡng, sớm hơn việc người dùng tự phát hiện.
  - Thêm health-check định kỳ cho RAG/vector store để phát hiện degradation trước khi ảnh hưởng traffic thật.
  - Viết thêm test đo throughput dưới tải đồng thời (concurrency test) trong CI để phát hiện sớm vấn đề "giả song song" như trường hợp này, tránh việc một request chậm kéo chậm toàn bộ hệ thống.
  - Cân nhắc thêm timeout + circuit breaker cho tầng RAG retrieval, tránh một dependency chậm làm nghẽn toàn bộ luồng xử lý.

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Lê Kiên Cường | Logging & PII (correlation ID middleware, structured logging, PII scrubbing) | _(điền link commit)_ | _(điền)_ |
| | | | |