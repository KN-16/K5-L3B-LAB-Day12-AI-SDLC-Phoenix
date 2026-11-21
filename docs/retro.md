# Retro nhóm

## Phase 1

- Mẫu kho cho phép Gather và Quán chạy kiểm chứng riêng. Bản tích hợp qua smoke hai tiến trình và chạy lặp lại phiên phục vụ với output giống từng byte.
- Review HUD phát hiện snapshot thiếu bộ đếm có thể tạo nhãn `NaN:NaN`. Đã sửa và kiểm lại với cả trường hợp thiếu giá trị và giá trị số.
- Việc mang sang Phase 2. Khôi chốt tuning và giao diện chuyển pha trước khi gộp phần dùng chung. Diên và Nhân giữ fixture riêng để kiểm hai ca trước smoke tích hợp.

## Phase 2 (nhanh)
- Hợp đồng kho đếm và giao diện chuyển pha giúp Gather, Quán và Session phát triển riêng. Khi ghép, file kho và snapshot Quán tick 0 khớp, kể cả hai nguyên liệu mới.
- Bật v1.1 làm lộ ba giả định test cũ về số đàn cá, chế độ `day` và nút `attack`. Nhóm cần đối chiếu những kỳ vọng phụ thuộc version với Ticket-02 khi đổi manifest.
- Phase 3, Khôi chuẩn bị cặp fixture kho v1.1/v1.2 trước khi sửa adapter. Diên và Nhân dùng cùng fixture để kiểm bàn giao từ Gather sang Quán. Khôi kiểm cả lỗi nhận schema cũ và smoke kho mới trước khi gắn tag.

## Phase 4 (cuối)

- Hành động Phase 2 đã được thực hiện. Nhóm lập ADR cùng hai fixture kho, kiểm CLI v1.2 trả mã 2 với kho đếm và so file kho mới với snapshot Quán.
- Hai PR đầu Phase 3 giữ v1.1, giúp gộp adapter và Quán riêng. Bản tích hợp vẫn cần bổ sung phần Gather để kiểm schema mới từ đầu đến cuối.
- Diên gửi file kho Gather để Nhân kiểm bếp. Nhân bàn giao test Quán để Khôi chạy hồi quy tích hợp. Hai bạn ghi lại việc phối hợp trong phản tư cá nhân. [Diên](members/dinhphucdien179.md) · [Nhân](members/ying684.md)
- Qua tag `phase-3`, Khôi có 8, Diên 6 và Nhân 3 commit nội dung. Ma trận kiểm chứng dẫn các commit đại diện. Token và chi phí chưa đo.
- Một lỗi của bản HUD do AI hỗ trợ là hiện `NaN:NaN` khi snapshot thiếu bộ đếm kiên nhẫn. Kiểm diff rồi dựng fixture thiếu giá trị để tái hiện. Sau sửa, chạy lại năm ca trạng thái khách.
- Khôi giữ smoke bàn giao bằng CLI thật ngay cạnh test từng module và kiểm gói Release từ thư mục mới giải nén trước khi đăng GitHub.
