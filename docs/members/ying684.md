# ying684 — phản tư cá nhân (≤ 200 từ)

- **Tôi đã làm (kèm link commit)** — Phụ trách Mở Quán qua ba phase.
  - P1 làm khách, giữ nguyên liệu, nấu, phục vụ và thanh toán. [`152b635`](https://github.com/KN-16/K5-L3B-LAB-Day12-AI-SDLC-Phoenix/commit/152b635)
  - P2 kiểm quán với hai bếp, bốn bàn, sáu món và lọc món theo kế hoạch ngày. [`6a5ccab`](https://github.com/KN-16/K5-L3B-LAB-Day12-AI-SDLC-Phoenix/commit/6a5ccab)
  - P3 giữ hàng theo ID, cấp lại khi hàng ươn và chốt giá theo độ tươi. [`e58cd7a`](https://github.com/KN-16/K5-L3B-LAB-Day12-AI-SDLC-Phoenix/commit/e58cd7a)
- **Tôi đã review (kèm link)** — Tôi kiểm phần Quán bằng kho Gather của Diên và bàn giao các test Quán qua PR để Khôi chạy hồi quy tích hợp. [Bằng chứng Phase 1](../verification/phase-1.md) · [Bằng chứng Phase 3](../verification/phase-3.md)
- **AI sai ở đâu và tôi phát hiện thế nào** — Bản đầu tính boa bằng số thực nên 58% của 50 bị làm tròn xuống 28. Ca test kỳ vọng 29 phơi ra lỗi. Sau khi đổi sang phép tính thập phân, test đạt.
- **Điều tôi học được** — Viết test ở đúng tick biên và kiểm số tiền nguyên để phát hiện lỗi mà một lượt chơi thử dễ bỏ sót.
