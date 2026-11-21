# Kiểm chứng Phase 4 Phoenix

Bản ứng viên Test Contract v1.3 trên nền tag `phase-3` tại `139791b`. Chạy lệnh bằng Python trong `.venv` của nhóm trên Windows. Khôi review kết quả và xác nhận lại trên commit bàn giao trước khi gắn tag.

| AC | Bằng chứng | Kết quả |
|---|---|---|
| AC-P4-01 — Benchmark Canvas | [`bench.json`](../proof/phase-4/bench.json). Chạy `python3 -m chonoi.bench --seed 42 --duration 30 --out tmp/bench.json` với Canvas 1280×720 và 3 giây làm nóng. | Đạt. 1.802 khung hình trong 30,014 giây, trung bình 60,04 FPS, 1% low 52,31 FPS, tải đến khung đầu 779 ms trên máy kiểm thử. |
| AC-P4-02 — Soak 10 Ngày | [`soak.json`](../proof/phase-4/soak.json) và [`soak-repeat.json`](../proof/phase-4/soak-repeat.json) từ hai lượt `python3 -m chonoi.soak --seed 7 --days 10 --out tmp/soak.json`. | Đạt 10/10 Ngày, 0 crash cả hai lượt. Các kết quả gameplay giống nhau. Ngày 10 có tổng thu 258, uy tín 4,2 và điểm 658. |
| AC-P4-03 — Cảnh báo tương phản cao | [`warnings.txt`](../proof/phase-4/warnings.txt). Chrome headless bật nút tương phản qua giao diện thật và đọc nhãn Canvas ở hai kịch bản cố định. | Đạt cả ba cảnh báo bằng chữ: thủy quái, oxy sắp hết và khách sắp giận. |
| AC-P4-04 — Gói chạy sạch | [`clean-source.txt`](../proof/phase-4/clean-source.txt), [README](../../README.md), [ghi chú Release](../release/v1.0.0.md) và [Credits](../../CREDITS.md). | Khởi động giao diện từ bản nguồn sạch trên Windows. Còn chạy kiểm trên macOS hoặc Linux, đóng gói từ tag và đính kèm ZIP khi phát hành. |
| AC-P4-05 — Hồi quy và bàn giao | [`tests.txt`](../proof/phase-4/tests.txt), [retro](../retro.md), [Phase 3](phase-3.md) và [nhật ký AI](../ai-usage-log.md). | 136/136 test đạt. Retro đã rà hành động Phase 2. Đủ ba phản tư trong `docs/members/`. Khôi review bản bàn giao trước khi gắn tag và phát hành. |

Một lượt chơi tự động với Chrome headless đi qua Lặn & Hái, nấu, giao và thu 70 nghìn ở Mở Quán, rồi mua bình oxy và đóng Shop để hiện tổng kết. Lượt thử bật tương phản cao và dùng ca rút ngắn. [Log trình duyệt](../proof/phase-4/browser-day.txt) · [Scenario](../proof/phase-4/browser.scenario.json)

## Bằng chứng đóng góp trước lần tích hợp cuối

| Thành viên | Việc và commit đại diện |
|---|---|
| [Khôi (`KN-16`)](../members/KN-16.md) | Kickoff và hợp đồng kho `d8d77a0`, HUD Phase 1 `595d800`, smoke và bằng chứng Phase 1 `ad79355`, tích hợp và kiểm chứng Phase 3–4. |
| [Diên (`dinhphucdien179`)](../members/dinhphucdien179.md) | Bàn giao kho Gather Phase 1 `c93888f`, xử lý Gather Phase 2 `c72aecf`, adapter kho cá thể Phase 3 `6e12f33`. Phản tư và nhật ký AI `4421e29`. |
| [Nhân (`ying684`)](../members/ying684.md) | Quán Phase 1 `152b635`, Quán Phase 2 `6a5ccab`, giữ chỗ và giá theo độ tươi Phase 3 `e58cd7a`. Phản tư và nhật ký AI `59e9acd`. |
