# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: high_latency_p95
- Severity: warning
- SLI/SLO liên quan: `latency_p95_ms` (objective 3000ms, target 99.5% requests — theo `config/slo.yaml`)
- Điều kiện và thời gian duy trì: `latency_p95 > 3000ms` duy trì liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng chờ phản hồi chatbot lâu hơn bình thường, trải nghiệm chậm, có thể bỏ dở phiên hoặc gửi lại câu hỏi (retry), làm tăng tải hệ thống thêm.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard Latency (P50/P95/P99), so sánh P50 và P95 — nếu chỉ P95 tăng còn P50 bình thường thì khả năng cao là một nhóm nhỏ request bị chậm (ví dụ do RAG timeout), không phải toàn hệ thống quá tải.
  2. Vào Langfuse, lọc traces theo khoảng thời gian alert kích hoạt, mở waterfall của các trace latency cao nhất để xác định span nào chiếm phần lớn thời gian (`retrieve` hay `generate`).
  3. Tra log theo `correlation_id` của các request chậm trong `data/logs.jsonl` để xem có lỗi, retry hoặc timeout đi kèm không.
- Mitigation tạm thời: Nếu do một dependency cụ thể chậm bất thường (ví dụ RAG), giảm concurrency traffic tạm thời hoặc bật timeout ngắn hơn kèm fallback response để tránh dồn ứ request.
- Owner: on-call-engineer

## Alert 2

- Tên: elevated_error_rate
- Severity: critical
- SLI/SLO liên quan: `error_rate_pct` (objective dưới 2%, target 99.0% — theo `config/slo.yaml`)
- Điều kiện và thời gian duy trì: `error_rate_pct > 5` duy trì liên tục trong 3 phút
- Ảnh hưởng tới người dùng: Một tỷ lệ đáng kể request trả về lỗi (HTTP 500), người dùng không nhận được câu trả lời, có thể mất niềm tin vào hệ thống hoặc phải thử lại nhiều lần.
- Ba bước kiểm tra đầu tiên:
  1. Gọi `/metrics` xem `error_breakdown` để xác định loại lỗi nào đang chiếm đa số (timeout, exception cụ thể, hay lỗi tập trung ở một feature).
  2. Tra log với `level: error`, lọc `event: request_failed`, xem `error_type` và `payload.detail` để hiểu nguyên nhân gốc.
  3. Kiểm tra dependency ngoài (Langfuse, mock LLM/RAG) và tài nguyên hệ thống xem có đang gián đoạn hoặc bị giới hạn không.
- Mitigation tạm thời: Nếu lỗi tập trung vào một feature/incident cụ thể, tạm thời disable qua endpoint `/incidents/{name}/disable` để giảm tác động trong lúc điều tra root cause.
- Owner: on-call-engineer

## Alert 3

- Tên: cost_budget_exceeded
- Severity: warning
- SLI/SLO liên quan: `daily_cost_usd` (objective dưới $2.5/ngày, target 100.0% — theo `config/slo.yaml`)
- Điều kiện và thời gian duy trì: `daily_cost_usd > 2.5` (kích hoạt ngay khi vượt ngưỡng trong ngày)
- Ảnh hưởng tới người dùng: Không ảnh hưởng trực tiếp ngay lập tức đến trải nghiệm, nhưng nếu không kiểm soát có thể dẫn đến việc phải giới hạn tính năng hoặc tắt dịch vụ đột ngột khi vượt ngân sách vận hành.
- Ba bước kiểm tra đầu tiên:
  1. Gọi `/metrics`, xem `total_cost_usd` và `avg_cost_usd` để xác định chi phí tăng do tần suất request cao hay do từng request tốn nhiều token hơn bình thường.
  2. Xem `tokens_in_total` / `tokens_out_total` để biết token input hay output đang chiếm phần lớn chi phí (output đắt hơn input theo công thức trong `agent.py`).
  3. Kiểm tra Langfuse traces xem có request bất thường (message quá dài, hoặc lỗi khiến agent sinh output lặp/quá dài, ví dụ incident `cost_spike`) không.
- Mitigation tạm thời: Giới hạn tạm thời độ dài input/output tối đa mỗi request, hoặc tạm dừng traffic không thiết yếu (ví dụ load test practice) cho đến khi xác định nguyên nhân.
- Owner: team-lead