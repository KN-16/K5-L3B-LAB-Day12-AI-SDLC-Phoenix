# Kế hoạch Phase 4 Phoenix

Khôi phụ trách triển khai tích hợp, benchmark, soak, tương phản cao, bằng chứng và chuẩn bị Release. Mỗi thành viên tự viết và xác nhận phản tư của mình trong `docs/members/<handle>.md`. Phase 4 giữ luật chơi và kho cá thể v1.2, khai Test Contract v1.3.

| AC | Nội dung bàn giao |
|---|---|
| AC-P4-01 | Benchmark thực sự vẽ Canvas 1280×720 tại bến, seed 42, làm nóng 3 giây, đo 30 giây và tạo đủ 5 trường. |
| AC-P4-02 | Soak seed 7 chạy 10 Ngày trong một Session, giữ trạng thái xuyên Ngày, lặp kế hoạch và cho kết quả gameplay lặp lại. |
| AC-P4-03 | Các cảnh báo thủy quái, oxy và khách đều đọc được trong chế độ tương phản cao. |
| AC-P4-04 | Từ thư mục nguồn sạch, chạy GUI bằng lệnh README. Chuẩn bị ZIP, ghi release notes, rà CREDITS và CHANGELOG. |
| AC-P4-05 | Hồi quy P1–P3, ma trận, kiểm lại hành động Phase 2 và phản tư. Khôi gắn `phase-4` và `v1.0.0` cùng SHA trên `main`, rồi đăng Release và gói ZIP. |

Tag `phase-3` đã chốt v1.2 tại `139791b` trên `main`. Khôi thực hiện Phase 4 từ `phoenix/p4-release` và gộp PR riêng để giữ hai mốc bàn giao.

Khôi kiểm và đẩy tag `phase-4` trước bước đóng gói. Khi phát hành, chọn đúng commit đó cho Release `v1.0.0`.
