# Nhật ký dùng AI (theo phase và theo người)

| Phase | Người | Công cụ / model | Việc | Token / chi phí ước tính | Ghi chú (AI sai ở đâu?) |
|---|---|---|---|---|---|
| 1 | Khôi | Codex | Hỗ trợ đối chiếu PRD-0 với starter, gợi ý phân công và soạn nháp kickoff, hợp đồng tích hợp | Chưa đo | Khôi báo đã xác nhận và đưa kickoff `d8d77a0` lên `main`. |
| 1 | Khôi | Codex | Hỗ trợ triển khai HUD hai ca, soạn hướng dẫn chạy và kiểm thử với snapshot mẫu | Chưa đo | Review phát hiện khi thiếu bộ đếm kiên nhẫn HUD có thể hiện `NaN:NaN`. Bản sửa đã được gộp và chạy lại trên bản tích hợp. |
| 1 | Khôi | Codex | Hỗ trợ chạy hồi quy, smoke bàn giao kho và kiểm HUD với Chrome headless trên `b772097` | Chưa đo | Lưu kết quả thật trong `docs/proof/phase-1/`. Khôi review ma trận trước khi gắn tag. |
