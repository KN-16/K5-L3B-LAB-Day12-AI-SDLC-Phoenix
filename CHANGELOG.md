# Changelog

## Phase 4 · Test Contract v1.3 · Release v1.0.0

- Thêm chế độ tương phản cao và nhãn cảnh báo thủy quái, oxy sắp hết và khách sắp giận.
- Khai benchmark Canvas 1280×720 và soak headless nhiều Ngày. Soak dùng chung Session và lặp kế hoạch D1–D5.
- Chuẩn bị gói Release chạy bằng Python 3.12 trở lên và trình duyệt. Gameplay, tuning và kho cá thể theo v1.2.

## Phase 3 · Test Contract v1.2

- Theo dõi từng nguyên liệu bằng ID và độ tươi. Gather và Quán hao tươi theo nhịp riêng. Quán giữ hàng theo ID, cấp lại khi ươn và chốt giá theo độ tươi lúc nấu.
- Thay đổi schema kho. `items` chuyển từ map số lượng sang mảng `{id,kind,fresh}`, kho rỗng là `{"items":[]}`. CLI v1.2 trả mã 2 với kho đếm. Dùng tag `phase-2` để chạy fixture theo schema cũ.
- Fixture v1.2 dùng mảng cá thể trong `gather.hold` và `quan.stock`, dùng mảng ID trong `customers[].reserved`. JSONL ghi cá thể trong `hold`, `stock`, sự kiện rơi hàng và các nguyên liệu đã dùng để nấu.

## Phase 2 · Test Contract v1.1

- Thêm cá bơi, Cá Sấu Năm Chèo, hai bếp, bốn bàn và thực đơn sáu món.
- Thêm vòng ngày, Shop, pause, cấp oxy và Máu, cùng chế độ `day` trên trình duyệt và headless.

## Phase 1 · Test Contract v1.0

- Hai ca Lặn & Hái và Mở Quán chạy riêng, bàn giao bằng file kho đếm.
- Hoàn thành HUD, kiểm gameplay và smoke hai tiến trình.
