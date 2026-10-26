# Cải tiến khung chỉnh phối cảnh — 20/10/2026

Đã nối khớp lại cạnh hiện có với nới có giới hạn các cạnh còn cắt mask.
Giữ nguyên checkpoint, protocol, RGB và mask segmentation/hư hại nguồn.

## Thuật toán

- Giữ nguyên tứ giác đã bao phủ ít nhất 98% mask gốc.
- Tính khoảng cách có dấu của pixel mask tới từng cạnh. Dùng phân vị với
  ngân sách pixel nằm ngoài chia cho bốn cạnh; tránh kéo khung theo vài ngoại lai.
- Chỉ dịch song song cạnh thiếu, lấy giao điểm thành góc mới. Tìm hệ số chung
  nhỏ nhất của các khoảng dịch đề xuất đạt mục tiêu raster. Cạnh đủ giữ nguyên.
- Từ chối phương án vượt giới hạn dịch cạnh/góc, diện tích, nền hoặc biên ảnh.
  Không kẹp riêng góc mới về biên vì sẽ thay đổi hướng cạnh.
- Kiểm tra nới khung và severity dùng mask gốc. Closing trong bước lấy đường
  biên cũ chỉ xử lý bản sao, không sửa mask đưa vào model hoặc phép đo.
- Phương án bị từ chối trả lại khung trước nới cùng lý do. Các kiểm tra hình học,
  che/cắt/nhiều máy hiện có tiếp tục quyết định có được phân cấp hay không.
- Góc đã nới vẫn là xấp xỉ từ mask, kể cả API được cung cấp tỷ lệ mặt máy.
  Giới hạn `surface_corners_approximated_from_mask` được ghi trong kết quả.

Cấu hình `image-processing/defect_vision/corner_expansion.v1.json`, phiên bản
`corner-expansion-v1-unvalidated`, **các ngưỡng thử nghiệm chưa kiểm chứng**:

| Ràng buộc | Giá trị |
|---|---:|
| Bao phủ mask tối thiểu / mục tiêu | 98% / 98,5% |
| Dịch cạnh tối đa / cạnh ngắn ước lượng | 10% |
| Dịch góc tối đa / cạnh ngắn ước lượng | 20% |
| Diện tích tứ giác mới / tứ giác trước nới | ≤ 1,25 |
| Phần ngoài mask trong tứ giác mới | ≤ 8% |

Thang kích thước lấy cạnh dài hơn trong mỗi cặp cạnh đối diện, rồi lấy cạnh
ngắn hơn của hai giá trị, cùng quy ước với kích thước đích perspective.
Sai số raster có thể lệch nhẹ mục tiêu nhưng không được dưới mức tối thiểu.

## Kết quả thực tế

Đã gửi lại hai capture qua BE → worker/checkpoint thật → database → GET/PNG:

| Nhãn app | Bao phủ trước | Bao phủ sau | Ngoài mask trong khung mới | Pixel hư hại gốc | Kết quả mới |
|---|---:|---:|---:|---:|---|
| front | 90,785% | 98,507% | 4,000% | 34021 | estimated / severe |
| back | 88,632% | 98,570% | 4,525% | 36344 | estimated / severe |

Hai capture thực tế đều chụp lại hình mặt trước trên màn hình laptop; `back`
là nhãn bước chụp, không phải kết luận model nhận diện mặt máy.

- Mask thân máy và hư hại nguồn trước/sau bằng nhau từng pixel.
- Mask sau warp bằng chính xác `warpPerspective(..., INTER_NEAREST)` với H và
  kích thước đích trong JSON; ảnh/overlay/mask khớp kích thước.
- Hai request chạy đúng hai lần detector. Worker xử lý khoảng 1,5–1,6 giây/ảnh
  trong lượt này, chưa gồm khởi tạo model. JSON lưu/đọc lại giữ nguyên.
- Kết quả vẫn có `needs_review=true`, `heuristic_unvalidated=true`, cơ sở
  `image_geometry` và giới hạn tỷ lệ/quan sát/góc xấp xỉ.
- 108 kiểm thử Python đạt, gồm giữ khung tốt, nới đúng cạnh, độ phân giải,
  ngoại lai, giới hạn nền/diện tích/dịch góc, giao điểm vượt ảnh và warp.
- Script model thật chạy ba ảnh mẫu và ảnh trắng: một lần khởi tạo engine,
  bốn request/bốn lần detector, cùng instance; đối chiếu độc lập mask đạt.
- Đã dừng các worker cũ trùng cổng và chạy một worker mới. Server chặn bind
  trùng trên Windows bằng `SO_EXCLUSIVEADDRUSE`; `/health` có `corner_config_version`.

Bằng chứng tại `image-processing/outputs/corner-expansion-verification/`:
`comparison.json`, `capture_front-comparison.png`, `capture_back-comparison.png`,
`backend-replay.json`, PNG/JSON theo scan ID và log worker.
Báo cáo singleton/parity: `image-processing/outputs/damage-verification/verification.json`.
Output được ignore; các bản ghi cũ được giữ nguyên.

## Chạy lại

Trong `image-processing`, dùng môi trường Python đang hoạt động:

```powershell
& D:\XuLiAnh\.venv\Scripts\python.exe -m pytest tests -p no:cacheprovider --basetemp outputs/pytest-corner-check -q
& D:\XuLiAnh\.venv\Scripts\python.exe scripts/verify_damage_integration.py
```

So sánh ba bước cũ/khớp lại/nới cạnh (thay đường dẫn ảnh/mask):

```powershell
python scripts/compare_perspective.py --case sample path/to/source.png path/to/body_original.png --output-dir outputs/corner-audit
```

Gửi lại capture cũ qua BE đang chạy; script tạo bản ghi kiểm thử mới:

```powershell
python scripts/verify_corner_expansion.py --case front outputs/damage-api/f75050dd-bc0e-4ca7-8702-a836afbfba3a/result.json --case back outputs/damage-api/46ce3131-4183-487e-99ec-b96dc2c8099e/result.json
```

Chỉ chạy một worker cổng 8000. Nếu cần khởi động lại sau khi tắt máy:

```powershell
& D:\XuLiAnh\.venv\Scripts\python.exe -m defect_vision.damage_api --port 8000 --device cpu
```

BE/Flutter dùng API cũ, không cần build lại. Cần phân tích lại ảnh để có kết quả
mới; lịch sử cũ giữ nguyên. `assets.corners` có viền mask xanh lá, tứ giác vàng,
pixel mask ngoài khung tô đỏ. Audit tại `severity.geometry_diagnostics.corner_expansion`.

## File của thay đổi này

- Mới: `image-processing/defect_vision/corner_expansion.py`, `corner_expansion.v1.json`.
- Sửa: `image-processing/defect_vision/phone_segmenter.py`, `damage_service.py`, `damage_api.py`.
- Kiểm tra: `image-processing/tests/test_corner_expansion.py`, `test_damage_integration.py`;
  `image-processing/scripts/compare_perspective.py`, `verify_corner_expansion.py`.
- Tài liệu: `docs/CORNER_EXPANSION.md`, `docs/PHONE_DAMAGE_V3.md`.

Nới khung không khôi phục mask thiếu, phần ngoài ảnh hoặc bị che; không sửa
được hướng cạnh sai nghiêm trọng. Bao phủ mask cao không chứng minh segmentation
hoặc góc vật lý đúng. Chưa có nhãn mức độ của con người nên không báo accuracy.
