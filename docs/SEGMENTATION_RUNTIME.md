# Kiến trúc runtime: Damage-mask segmentation

## Quyết định

Prototype chính thức sử dụng **phone segmentation + damage-mask segmentation**, không
dùng YOLO bounding box ở runtime. Quyết định này phản ánh đúng model/checkpoint, API
và Flutter đang có; không suy diễn rằng một baseline YOLO CLI là model đã bàn giao.

## Luồng xử lý

```text
Camera hoặc gallery
  -> Spring Boot POST /api/detections
  -> Python POST /analyze
  -> chuẩn hóa EXIF, RGB gốc
  -> phone segmentation
  -> damage-mask inference trên ảnh gốc
  -> geometry/severity heuristic (nếu đủ bằng chứng)
  -> source, mask và overlay PNG
  -> PostgreSQL history
  -> Flutter hiển thị overlay và lý do cần kiểm tra
```

Worker tạo mask nhị phân ứng viên hư hại trong cùng hệ tọa độ với ảnh nguồn.
Perspective/illumination chỉ phục vụ đo hình học, trực quan hóa hoặc so sánh; chúng
không được đưa ngược vào model damage hiện tại khi chưa có benchmark chứng minh lợi ích.

## API và UI được phép khẳng định

- `damage.found=true`: số pixel ứng viên đạt ngưỡng báo ảnh hiện hành; đây không phải
  xác nhận cuối cùng của kỹ thuật viên.
- `severity.estimated_severity`: chỉ là mức ước tính heuristic. Khi có
  `needs_review=true`, UI phải yêu cầu kiểm tra lại.
- `assets.overlay`: ảnh phủ vùng ứng viên từ mask, không phải bounding box.
- `detections`: hiện luôn là mảng rỗng trong runtime. App không được dựng class lỗi,
  confidence lỗi, kích thước mm hoặc bounding box từ dữ liệu giả.
- `phone_confidence`: là confidence của bước phân vùng điện thoại, không phải độ tin
  cậy rằng vùng ứng viên là hư hại.

## Những gì còn thiếu để đánh giá khoa học

Trước khi báo cáo chất lượng model, cần một test set độc lập có mask ground truth.
Mỗi mẫu phải ghi nguồn, license, thiết bị/mặt quan sát, nhãn normal/defective và không
được rò rỉ ảnh cùng một thiết bị/phiên chụp giữa train/validation/test.

Metric cần báo cáo:

| Mức | Metric |
|---|---|
| Pixel/mask | IoU, Dice/F1, pixel precision, pixel recall |
| Ảnh | image-level precision, recall, FPR, FNR, confusion matrix |
| Hệ thống | preprocessing, inference, postprocessing, total time |

Không dùng mAP bbox làm metric chính cho runtime này. Nếu sau này tích hợp YOLO thật,
đó là một nhánh kiến trúc mới cần model, annotation bbox, contract, UI và benchmark riêng.

## Failure cases phải demo

1. Điện thoại không được tìm thấy.
2. Ảnh bị che, cắt biên hoặc nhiều điện thoại.
3. Phản chiếu, viền máy hoặc noise bị đề xuất nhầm là ứng viên.
4. Hư hại nhỏ/bị blur không được tìm thấy.
5. Hình học mặt quan sát không đủ để ước tính severity.

Trong các trường hợp này, hệ thống phải giữ trạng thái `needs_review` hoặc
`insufficient_evidence`; không được kết luận thiết bị lành chỉ vì inference không đủ tin cậy.
