# Nhật ký dùng AI (theo phase và theo người)

| Phase | Người | Công cụ / model | Việc | Token / chi phí ước tính | Ghi chú (AI sai ở đâu?) |
|---|---|---|---|---|---|
| 1 | Khôi | Codex | Đối chiếu PRD-0 với starter, gợi ý phân công và soạn nháp hợp đồng tích hợp | Chưa đo | Khôi xác nhận nội dung kickoff và đẩy commit `d8d77a0` lên `main`. |
| 1 | Khôi | Codex | Hỗ trợ triển khai HUD hai ca, viết hướng dẫn chạy và kiểm với snapshot mẫu | Chưa đo | Bản HUD ban đầu có thể hiện `NaN:NaN` khi thiếu bộ đếm kiên nhẫn. Sau khi sửa, kiểm lại 5 tình huống hiển thị. |
| 1 | Khôi | Codex | Hỗ trợ chạy hồi quy, smoke bàn giao kho và kiểm HUD bằng Chrome headless trên `b772097` | Chưa đo | 72/72 test đạt. [Bằng chứng Phase 1](proof/phase-1/). |
| 2 | Khôi | Codex | Trích số liệu Ticket-02, lập tiêu chí chấp nhận và soạn nháp giao diện Gather, Quán, Shop | Chưa đo | Đối chiếu 6 món, 6 nguyên liệu và lượng nguyên liệu cần cho Ngày 1–5 với Ticket-02. |
| 2 | Khôi | Codex | Hỗ trợ triển khai vòng ngày, Shop, pause, CLI và giao diện trình duyệt | Chưa đo | Kiểm từng bước bằng fixture, sau đó kiểm lại vòng ngày với Gather và Quán đã tích hợp. |
| 2 | Khôi | Codex | Hỗ trợ bật v1.1, cập nhật hồi quy và chạy smoke | Chưa đo | Ba kỳ vọng P1 được cập nhật theo Ticket-02 về số đàn cá mặc định, mode `day` và cách xử lý `attack` khi tắt mở rộng. Bộ hồi quy đạt 110/110 test. [Bằng chứng Phase 2](proof/phase-2/). |
| 3 | Khôi | Codex | Đối chiếu Ticket-03, chuẩn bị fixture, soạn nháp ADR và phân công cho ba PR | Chưa đo | Khôi review schema, giao diện và tiêu chí kiểm trước khi bàn giao. |
