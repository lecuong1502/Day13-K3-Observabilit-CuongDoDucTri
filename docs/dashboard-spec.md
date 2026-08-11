# Yêu cầu dashboard

Contract có thể kiểm tra bằng máy nằm tại `config/dashboard.yaml`. Hướng dẫn dựng và kiểm tra runtime nằm tại [DASHBOARD_SETUP.md](DASHBOARD_SETUP.md).

Dashboard chính cần đủ 6 nhóm thông tin:

1. Latency P50/P95/P99.
2. Traffic: request count hoặc QPS.
3. Error rate và breakdown theo loại lỗi.
4. Cost theo thời gian.
5. Tổng token input/output.
6. Quality proxy.

Tiêu chuẩn trình bày:

- Khoảng thời gian mặc định: 1 giờ.
- Tự refresh mỗi 15–30 giây nếu công cụ hỗ trợ.
- Có threshold hoặc SLO line.
- Ghi rõ đơn vị.
- Chỉ giữ 6–8 panel quan trọng ở lớp chính.
- Screenshot phải nhìn được tên panel và khoảng thời gian.

Kiểm tra contract trước khi chụp evidence:

```bash
python scripts/validate_dashboard.py
```

---

## Chi tiết 6 panel (nhóm Cường Độ Đức Trí)

Công cụ sử dụng: dashboard mô tả qua spec này, dữ liệu lấy trực tiếp từ endpoint `/metrics` (nguồn `data/logs.jsonl` khi cần đối chiếu). Nếu dùng Grafana/Langfuse để trực quan hóa, thay panel nguồn bằng dashboard tool tương ứng nhưng vẫn giữ đúng 6 nhóm và ngưỡng SLO bên dưới.

| # | Panel | Nguồn field (`/metrics`) | Loại biểu đồ | Đơn vị | Khoảng thời gian | Threshold / SLO line |
|---|---|---|---|---|---|---|
| 1 | Latency P50/P95/P99 | `latency_p50`, `latency_p95`, `latency_p99` | Line chart (3 series) | ms | 1 giờ, refresh 15s | SLO line tại 3000ms cho P95 (theo `config/slo.yaml`) |
| 2 | Traffic | `traffic` | Counter / QPS gauge | số request (hoặc req/s) | 1 giờ, refresh 15s | Không có ngưỡng cứng — theo dõi xu hướng |
| 3 | Error Rate | `error_rate_pct`, `error_breakdown` | Single value (%) + bảng breakdown theo `error_type` | % | 1 giờ, refresh 15s | SLO line tại 2% (cảnh báo khi > 5% theo `alert_rules.yaml`) |
| 4 | Cost | `total_cost_usd`, `avg_cost_usd` | Line chart tích lũy theo thời gian | USD | 1 giờ (đối chiếu ngày cho cost_budget) | Ngưỡng $2.5/ngày theo SLO `daily_cost_usd` |
| 5 | Tokens | `tokens_in_total`, `tokens_out_total` | Bar chart (2 series input/output) | số token | 1 giờ, refresh 15s | Không có ngưỡng cứng — theo dõi xu hướng bất thường |
| 6 | Quality | `quality_avg` | Single value / gauge | điểm (0.0–1.0) | 1 giờ, refresh 30s | SLO line tại 0.75 theo `config/slo.yaml` |

### Ghi chú vận hành

- Toàn bộ 6 panel đọc trực tiếp từ `/metrics`; script `python scripts/validate_dashboard.py` dùng để kiểm tra contract kỹ thuật (đủ 6 panel, đúng field), không thay thế cho ảnh dashboard runtime thật.
- Time range mặc định 1 giờ giúp phát hiện bất thường gần thời điểm hiện tại; riêng panel Cost cần đối chiếu thêm theo ngày vì SLO `daily_cost_usd` tính theo chu kỳ 24h.
- Threshold/SLO line lấy trực tiếp từ `config/slo.yaml` để đảm bảo dashboard và alert rules nhất quán với nhau.