# Hướng dẫn Tự động hóa với n8n

Tài liệu này hướng dẫn bạn cách cài đặt và sử dụng **n8n** để tự động hóa quy trình lấy dữ liệu thời tiết cho dự án AgroSmart.
`
## 1. Cài đặt n8n (Yêu cầu Node.js)

Nếu bạn chưa cài Node.js, hãy tải và cài đặt từ [nodejs.org](https://nodejs.org/).

Sau đó, mở CMD hoặc Terminal và chạy lệnh sau để cài đặt và khởi động n8n:

```bash
npx n8n
```

Sau khi n8n khởi động, nhấn phím `o` để mở giao diện web (thường là `http://localhost:5678`).
## 2. Import Workflow

1.  Tại giao diện n8n, chọn menu **Workflows** -> **Import from File**.
2.  Chọn file `weather_automation.json` nằm trong thư mục `n8n/` của dự án này.
3.  Bạn sẽ thấy một quy trình (workflow) bao gồm các bước:
    *   **Schedule Trigger:** Kích hoạt tự động (ví dụ: hàng tuần).
    *   **Read Province CSV:** Đọc danh sách tỉnh thành từ file `data/vietnam_provinces_latlon.csv`.
    *   **Fetch NASA Data:** Gọi API NASA POWER để lấy dữ liệu thời tiết mới nhất.
    *   **Calculate Stats:** Tính toán trung bình nhiệt độ, lượng mưa, độ ẩm.
    *   **Save to CSV:** Lưu kết quả vào file `data/n8n_weather_update.csv`.
