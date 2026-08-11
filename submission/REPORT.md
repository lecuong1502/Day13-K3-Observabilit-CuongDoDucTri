# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: Cường Độ Đức Trí
- Repository URL: https://github.com/lecuong1502/Day13-K3-Observabilit-CuongDoDucTri
- Commit SHA cuối:  5fab7c88cc834abdc1f6064472d16e4eed5a0c1c
- Thành viên và vai trò:
  - Lê Kiên Cường — Metrics & Alerting / Tracing & Prompt Version / Incident Investigation
  - Xuân Thế Độ — Security & Compliance
  - Trần Công Đức — Logging & Middleware
  - Nguyễn Công Trí — QA & Incident Analyst

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: 30/100 (baseline CP0) → 100/100 (sau CP1)
- Tổng số traces: 10 trace runs (tương ứng 10 request qua `/chat`), mỗi trace gồm 3 observation lồng nhau (`run` → `retrieve` + `generate`) — tổng cộng 106+ observations trên Langfuse trong 1 ngày gần nhất (bao gồm các lần chạy load test lặp lại và batch challenge)
- Số PII leak còn lại: 0 theo `validate_logs.py`; đã tự kiểm tra thủ công qua `grep "REDACTED" data/logs.jsonl`, xác nhận email/phone/credit card được che đúng định dạng `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CREDIT_CARD]`
- Link/đường dẫn dashboard: dữ liệu lấy từ endpoint `http://localhost:8000/metrics`; contract 6 panel đã validate `HỢP LỆ: 6/6 panel` qua `python scripts/validate_dashboard.py`. Dashboard runtime dựng bằng Streamlit (`scripts/dashboard.py`), đọc trực tiếp từ `data/logs.jsonl`. Snapshot mẫu (baseline):
  - traffic: 10
  - latency_p50/p95/p99: 1486 / 1940 / 1940 ms
  - avg_cost_usd: 0.0019 | total_cost_usd: 0.019
  - tokens_in/out: 330 / 1199
  - error_rate_pct: 0.0
  - quality_avg: 0.88

## 3. Logging và tracing

- Evidence correlation ID: log có trường `correlation_id` dạng `req-<8hex>`, ví dụ `req-510167ed`, `req-1920bf0c`, gắn xuyên suốt từ `request_received` đến `response_sent` cho cùng một request, đồng thời được đính kèm vào metadata generation trên Langfuse để liên kết log ↔ trace.
- Evidence PII redaction: 3 dòng log mẫu đã che PII đúng định dạng:
  - `"What is your refund policy? My email is [REDACTED_EMAIL]"`
  - `"Here is my phone [REDACTED_PHONE_VN], what should be logged?"`
  - `"What is the policy for PII and credit card [REDACTED_CREDIT_CARD]?"`
  (lưu ảnh trong `submission/evidence/`)
- Evidence trace waterfall: ảnh chụp Tracing trên Langfuse Cloud (project Day13-K3), thấy rõ cấu trúc `run` (span cha) → `retrieve` (span RAG) + `generate` (span LLM, type GENERATION) lồng bên trong, mỗi trace có Start Time, Input, Output, Metadata riêng
- Giải thích một span đáng chú ý: Span `generate` (type GENERATION) mang thông tin quan trọng nhất cho việc điều tra sự cố — chứa `usage_details` (prompt_tokens/completion_tokens), `cost_details`, và metadata `prompt_version`/`prompt_label`/`correlation_id`. Khi kết hợp với `correlation_id` được gắn vào metadata của generation, ta có thể truy ngược từ một dòng log lỗi trong `data/logs.jsonl` sang đúng trace/span tương ứng trên Langfuse để xem input/output đầy đủ và thời gian xử lý — đây là mắt xích nối giữa Metrics (phát hiện bất thường) → Traces (khoanh vùng) → Logs (xác nhận root cause).

**Câu hỏi phản biện CP1:**
Khác biệt lớn nhất giữa log CP0 và CP1: log CP0 thiếu correlation_id (toàn bộ "MISSING"), thiếu enrichment (user_id_hash, session_id, feature, model), và dữ liệu nhạy cảm thô chưa được che ở tất cả các trường. Sau CP1, mọi log record có correlation_id duy nhất theo từng request, đầy đủ metadata ngữ cảnh, và PII được scrub ở toàn bộ field (không chỉ payload/event).

`clear_contextvars()` bắt buộc ở đầu middleware vì structlog dùng Python contextvars để chia sẻ context xuyên suốt một request mà không cần truyền tay qua từng hàm. Nếu không clear, context của request trước có thể bị request sau tái sử dụng (đặc biệt khi nhiều request được xử lý trên cùng event loop/thread), dẫn đến log sai lệch — correlation_id, user_id_hash, session_id của người dùng A có thể lẫn vào log của người dùng B, gây rò rỉ dữ liệu giữa các request.

## 4. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: version #1, label `baseline` + `production` (ban đầu). Nội dung:
  ```
  Feature={{feature}}
  Docs={{docs}}
  Question={{message}}
  ```
- Version/label candidate: version #2, label `candidate`. Nội dung bổ sung một dòng yêu cầu định dạng ngắn gọn:
  ```
  Feature={{feature}}
  Docs={{docs}}
  Question={{message}}
  Answer concisely in 2-3 sentences.
  ```
- Trace ID của mỗi version:
  - Baseline (label=`production`, version=`1`): `req-1c04d52a` (2026-08-11T04:46:43Z, session s01)
  - Candidate (label=`candidate`, version=`2`): `req-9e0ee376` (2026-08-11T04:50:20Z, session s01)

  Xác nhận qua console debug log trước khi đối chiếu trên Langfuse:
  ```
  [PROMPT DEBUG] name=day13-chat label=production version=1 source=langfuse   -> req-1c04d52a
  [PROMPT DEBUG] name=day13-chat label=candidate version=2 source=langfuse    -> req-9e0ee376
  ```

- Bằng chứng đổi label hoặc rollback: đã chuyển label `production` từ version #1 sang version #2 trên Langfuse Prompts UI (project Day13-K3), chạy lại request xác nhận trace mới nhận đúng `prompt_version: "2"`; sau đó rollback `production` về lại version #1. Ảnh trước/sau lưu tại `submission/evidence/prompt_versions.png` (danh sách 2 version với label) và `submission/evidence/prompt_rollback.png`.

> **Ghi chú kỹ thuật**: Trong quá trình test, gặp sự cố label không đổi dù đã sửa `.env` — nguyên nhân do biến `LANGFUSE_PROMPT_LABEL` đã được `export` thủ công vào shell từ trước, khiến `.env` mới không ghi đè được (python-dotenv mặc định không override biến đã tồn tại sẵn trong environment). Khắc phục bằng `unset LANGFUSE_PROMPT_LABEL` trước khi restart uvicorn. Đây là bài học thực tế về thứ tự ưu tiên giữa biến môi trường shell và file `.env`.

Mục tiêu phần này là khả năng truy xuất version và rollback có bằng chứng, không đánh giá prompt nào "hay hơn".

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: `HỢP LỆ: 6/6 panel có trong dashboard contract` (đạt)
- Evidence dashboard: dashboard runtime dựng bằng Streamlit (`scripts/dashboard.py`), đọc trực tiếp từ `data/logs.jsonl` theo đúng mapping trong `docs/dashboard-spec.md`:

  | Panel | Nguồn field | Đơn vị |
  |---|---|---|
  | Latency | `response_sent.latency_ms` (P50/P95/P99) | ms |
  | Traffic | `request_received` (count, req/phút) | request |
  | Errors | `request_received`, `request_failed`, `error_type` | % + breakdown |
  | Cost | `response_sent.cost_usd` | USD |
  | Tokens | `response_sent.tokens_in/tokens_out` | token |
  | Quality | `response_sent.quality_score` (mean) | điểm 0.0-1.0 |

  Snapshot baseline từ `/metrics`:
  - traffic: 10 | latency_p50/p95/p99: 1486/1940/1940 ms
  - avg_cost_usd: 0.0019 | total_cost_usd: 0.019
  - tokens_in/out: 330/1199 | error_rate_pct: 0.0 | quality_avg: 0.88

  _(Ảnh chụp dashboard runtime baseline và ảnh dashboard lúc bật incident `rag_slow` — lưu tại `submission/evidence/dashboard_baseline.png` và `submission/evidence/dashboard_incident_rag_slow.png`)_

- SLO đã chọn và lý do: Giữ nguyên giá trị mặc định trong `config/slo.yaml` vì phù hợp với đặc điểm hệ thống (fake LLM, chi phí thấp, dùng cho mục đích học tập):
  - `latency_p95_ms`: objective 3000ms, target 99.5% — đủ dư địa cho baseline (~1.5-2s) trong khi vẫn phát hiện được incident `rag_slow` (P95 thực tế lên đến 4292ms khi có sự cố, vượt rõ ràng ngưỡng này)
  - `error_rate_pct`: objective dưới 2%, target 99.0% — chuẩn phổ biến cho hệ thống nội bộ/giai đoạn học tập
  - `daily_cost_usd`: objective dưới $2.5/ngày — phù hợp ràng buộc chi phí thấp của lab (mock LLM, không tốn phí API thật)
  - `quality_score_avg`: objective ≥ 0.75 — dựa trên heuristic quality score thực tế trung bình đạt 0.86-0.88, có biên an toàn hợp lý

- Alert rules và runbook: 3 alert đã cấu hình trong `config/alert_rules.yaml`, đầy đủ runbook trong `docs/alerts.md`:
  1. `high_latency_p95` (warning) — `latency_p95 > 3000ms` trong 5 phút, owner: on-call-engineer
  2. `elevated_error_rate` (critical) — `error_rate_pct > 5` trong 3 phút, owner: on-call-engineer
  3. `cost_budget_exceeded` (warning) — `daily_cost_usd > 2.5`, owner: team-lead

  Cả 3 alert đều thiết kế symptom-based (dựa trên triệu chứng người dùng/SLO), không gắn vào tên hàm hay implementation cụ thể; mỗi runbook có đủ: điều kiện kích hoạt, ảnh hưởng người dùng, 3 bước kiểm tra đầu tiên, mitigation tạm thời, và owner rõ ràng.

**Câu hỏi phản biện CP2:**
Alert rules nên thiết kế dựa trên triệu chứng người dùng thấy (symptom-based) thay vì dựa vào tên hàm/lỗi implementation cụ thể vì:

1. Symptom-based alert (ví dụ "latency_p95 > 3000ms") phản ánh trực tiếp trải nghiệm thực tế của người dùng — khi alert nổ lên, ta biết ngay có vấn đề ảnh hưởng đến người dùng, bất kể nguyên nhân kỹ thuật bên dưới là gì.
2. Hệ thống có thể thay đổi implementation liên tục (đổi tên hàm, refactor, đổi thư viện) — nếu alert gắn chặt vào tên hàm cụ thể, alert sẽ dễ vỡ hoặc lỗi thời mỗi khi code thay đổi, trong khi ngưỡng triệu chứng (latency, error rate, cost) vẫn ổn định qua thời gian.
3. Symptom-based alert giảm nhiễu (alert fatigue): không phải mọi lỗi implementation đều ảnh hưởng đến người dùng, trong khi alert theo triệu chứng chỉ kích hoạt khi thực sự có tác động đáng kể và kéo dài.
4. Nó tách biệt "cái gì bị ảnh hưởng" (được alert cho biết) khỏi "tại sao bị ảnh hưởng" (được điều tra qua traces/logs sau đó) — đúng quy trình observability: Metrics phát hiện triệu chứng → Traces khoanh vùng → Logs xác nhận root cause.

## 6. Điều tra challenge

- Challenge ID: `day13-k3-observability-v1`
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

**Câu hỏi phản biện CP3:**
Bằng chứng khẳng định root cause đến từ việc đối chiếu 3 lớp độc lập cùng khớp nhau: Metrics cho thấy latency_p95 (4292ms) tăng đúng bằng với latency_ms ghi trong log của trace `req-ac019214`; log `incident_enabled` xác nhận thời điểm bật `rag_slow` xảy ra ngay trước batch request; và các timestamp `request_received`/`response_sent` liên tiếp không chồng lấn chứng minh thêm một vấn đề kiến trúc (blocking event loop) mà chỉ nhìn số liệu metrics tổng quát sẽ không thể phát hiện ra — phải có log timestamp chi tiết ở mức từng request mới nhìn ra được.

Nếu chỉ có metrics mà không có log chi tiết, nhóm sẽ chỉ biết "latency tăng" nhưng không thể phân biệt được đây là do RAG chậm theo thiết kế hay do vấn đề nghẽn cổ chai ở tầng xử lý concurrent — hai nguyên nhân này cần cách khắc phục hoàn toàn khác nhau (một cái cần sửa RAG backend, một cái cần sửa kiến trúc async), và nếu đoán sai sẽ sửa nhầm chỗ trong khi vấn đề thực sự vẫn còn nguyên.

## 7. Đóng góp cá nhân

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Lê Kiên Cường | Metrics & Alerting (error_rate_pct, SLO config, alert rules, runbook, dashboard contract); Tracing & Prompt Versioning  | https://github.com/lecuong1502/Day13-K3-Observabilit-CuongDoDucTri/commit/2cd2e8919d649d0f30bc535dc3e64b852fe95648 | Cách thiết kế alert symptom-based; kỹ thuật đối chiếu Metrics -> Traces -> Logs để xác định root cause; phát hiện vấn đề blocking event loop trong FastAPI async handler; quản lý biến môi trường (.env vs shell export) |
| Xuân Thế Độ | Security & Compliance (PII scrubbing patterns, redaction coverage toàn bộ log fields) | https://github.com/lecuong1502/Day13-K3-Observabilit-CuongDoDucTri/commit/3d4da89b1a0ebf3e01e9ade7b3d2de395d89aaf6 | Cách viết regex pattern để nhận diện dữ liệu nhạy cảm (email, số điện thoại VN, CCCD, thẻ tín dụng, hộ chiếu) mà không quá tay gây false positive; hiểu rằng validator tự động (`validate_logs.py`) chỉ kiểm tra mẫu cơ bản và không đảm bảo log sạch PII hoàn toàn — cần tự kiểm tra thủ công; nắm được nguyên tắc thứ tự xử lý trong pipeline logging (processor `scrub_event` phải đặt đúng vị trí giữa TimeStamper và JSONRenderer để không che nhầm timestamp nhưng vẫn che được dữ liệu trước khi ghi xuống file) |
| Trần Công Đức | Logging & Middleware (Correlation ID middleware, structured logging với structlog, JSON schema log) | https://github.com/lecuong1502/Day13-K3-Observabilit-CuongDoDucTri/commit/f858dbee331e772f336a680f892c8218050f7c47 | Cơ chế contextvars trong Python và cách structlog dùng nó để truyền context xuyên suốt một request mà không cần truyền tay qua từng hàm; tại sao phải gọi `clear_contextvars()` ở đầu mỗi request để tránh rò rỉ dữ liệu giữa các request khác nhau; cách middleware trong FastAPI/Starlette hoạt động ở tầng request/response, và cách gắn thêm header (`x-request-id`) để client cũng truy vết được request |
| Nguyễn Công Trí | QA & Incident Analyst (chạy pytest, validate scripts, hỗ trợ điều tra incident, viết báo cáo) | https://github.com/lecuong1502/Day13-K3-Observabilit-CuongDoDucTri/commit/aa8d010f8b4bc31aaa7c56bdb535c02c3c5aca1c | Quy trình điều tra sự cố chuẩn Metrics -> Traces -> Logs, và tại sao phải đối chiếu đủ cả ba lớp thay vì chỉ dựa vào một nguồn dữ liệu duy nhất; cách viết test tự động (pytest) để đảm bảo không phá vỡ hành vi cũ khi thêm tính năng mới (ví dụ test `test_agent_links_prompt_version_to_trace_and_generation` giúp phát hiện sớm khi thêm correlation_id vào sai chỗ trong metadata); kỹ năng tổng hợp bằng chứng kỹ thuật (log, trace ID, số liệu metrics) thành một báo cáo mạch lạc, có thể truy xuất lại được |