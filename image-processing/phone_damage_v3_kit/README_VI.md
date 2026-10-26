# Tích hợp phone damage v3 vào đồ án

Gói này chứa đúng checkpoint v3 và code suy luận hiện tại. Không chứa dataset, cache, phone_detect hoặc bộ chấm mức độ. Không có thao tác train khi import hoặc chạy ví dụ.

## 1. Copy những gì?

Copy nguyên thư mục `phone_damage_v3` vào thư mục backend Python của đồ án. Giữ nguyên cấu trúc bên trong:

```text
backend/
  phone_damage_v3/
    __init__.py
    damage_roi_engine.py
    damage_roi_inference.py
    phone_body_roi.py
    phone_damage_roi.py
    phone_semantic.py
    phone_data.py
    train_damage_roi.py
    weights/
      model.pt
      protocol.json
```

`train_damage_roi.py` được giữ vì engine dùng hàm `load_model` trong file này; import không chạy training. Không xóa file theo tên. Các import đã được đổi sang tương đối để tránh xung đột module với đồ án.

Copy thêm `example_integration.py`, `smoke_test.py`, `requirements-inference.txt` vào cùng cấp nếu muốn chạy ví dụ. Hai tài liệu README/prompt nên được copy theo để AI của đồ án đọc. Không cần copy `.venv`, `my_data`, `runs`, `artifacts`, model v2 hoặc các server demo.

Ứng dụng đã có phone_detect thì tiếp tục dùng checkpoint đó. Gói không cần bản sao detector khi `load_phone_detector=False`. Đối chiếu SHA256 checkpoint detector đang dùng với trường `phone_model_sha256` của `protocol.json`; checkpoint đã kiểm chứng là RF-DETR SegSmall, không phải YOLO.

## 2. Môi trường Python

- Dùng backend/worker Python để nạp model. Checkpoint là state_dict của kiến trúc PyTorch riêng, không dùng `YOLO(model.pt)` hoặc `torch.jit.load` để mở.
- Môi trường đã kiểm tra: Python 3.13.5; phiên bản thư viện thực tế ở `environment-tested.json`. Chưa bảo đảm cho mọi tổ hợp Python/PyTorch khác.
- Nếu backend đã có torch/torchvision hoạt động thì kiểm tra trước, tránh cài lại làm hỏng môi trường hiện có.
- Nếu cần môi trường mới, cài cặp PyTorch/torchvision tương thích với CPU/CUDA đích theo hướng dẫn chính thức. Sau đó cài phần còn lại bằng lệnh bên dưới. CPU vẫn dùng được, tốc độ cần đo trên máy đích.

```powershell
python -m pip install -r requirements-inference.txt
```

PyTorch/torchvision không nằm trong file requirements này để tránh ghi đè lựa chọn CPU/CUDA của đồ án. Gói đã được kiểm tra với torch 2.13.0+cu126 và torchvision 0.28.0+cu126. Đây là phiên bản trên máy nguồn, không phải yêu cầu tải wheel CUDA từ PyPI thông thường.

Luồng dùng mask ngoài không import/nạp RF-DETR, vì vậy không cần cài thêm RF-DETR cho chính damage worker nếu detector đã chạy ở nơi khác. Các module hỗ trợ có import PyYAML nên thư viện này vẫn được liệt kê.

## 3. Khởi tạo một lần

Ví dụ khi file gọi nằm ngay cạnh thư mục `phone_damage_v3`:

```python
from pathlib import Path
from phone_damage_v3 import ROIDamageEngine, PhoneNotFound

BASE = Path(__file__).resolve().parent
engine = ROIDamageEngine(
    BASE / 'phone_damage_v3' / 'weights',
    load_phone_detector=False,
    device='cpu',  # Hoặc 'cuda:0' khi môi trường GPU sẵn sàng.
)
```

Giữ engine trong service/worker dùng lại qua nhiều ảnh. Không tạo engine lại trong mỗi request. Nếu chạy nhiều process thì mỗi process sẽ có bản model riêng; tính bộ nhớ tương ứng. Engine hiện có khóa để tuần tự hóa lời gọi trên cùng instance.

## 4. Nối vào luồng ảnh

1. Chuẩn hóa hướng EXIF trước; giữ RGB gốc đúng hướng.
2. Detector hiện có chạy một lần để tạo mask điện thoại và bốn góc. Quy đổi về đúng tọa độ RGB gốc nếu detector dùng resize/letterbox.
3. Chọn đúng một điện thoại mục tiêu; không gộp nhiều máy thành một bề mặt để chấm mức độ.
4. Đưa RGB gốc và mask đó vào v3:

```python
damage_mask, candidate_pixels = engine.predict_with_body(
    rgb_original, phone_mask_original,
)
found = candidate_pixels >= engine.alarm_pixels
```

Đầu vào RGB: `numpy.uint8`, kích thước H×W×3, giá trị 0–255. Nếu đọc bằng OpenCV, chuyển BGR sang RGB. Mask thân máy H×W, bool hoặc số nguyên chỉ chứa 0/1/255; không truyền probability map hoặc bốn điểm thay mask.

Đầu ra `damage_mask`: bool H×W ở ảnh gốc; `candidate_pixels`: số pixel ứng viên, không phải độ tin cậy hoặc mức độ. Dùng `mask.astype('uint8') * 255` để lưu PNG. Dùng PNG/mảng để truyền mask, không dùng JPEG.

Thông số giữ nguyên: threshold 0,4; patch 512; overlap 128; context 512; body margin 0; variant native. Engine tự thực hiện chia patch, chuẩn hóa và ghép kết quả; không tự resize toàn ảnh xuống 512 trước khi gọi.

Quy tắc báo ảnh đang dùng là ít nhất 200 pixel ứng viên ở ảnh gốc, engine mặc định lấy 200 khi protocol cũ không có trường alarm_pixels. `found=False` không đồng nghĩa mask rỗng hoặc thiết bị lành. Giữ riêng cờ này với phép đo sau warp.

`PhoneNotFound`, mask sai tọa độ, lỗi model/hash hoặc lỗi tính toán phải trả trạng thái lỗi/không đủ dữ liệu; không chuyển thành kết quả không hư hại.

## 5. Liên kết chỉnh phối cảnh

Checkpoint hiện tại nhận ảnh gốc chưa nắn. Chạy v3 trước rồi áp cùng H và kích thước đích như RGB đã chỉnh lên mask hư hại và mask bề mặt quan sát. Mask dùng `INTER_NEAREST`; ảnh RGB dùng nội suy phù hợp cho ảnh.

Không dùng mask trước warp với ảnh sau warp. Mặt trước/sau/cạnh là các bề mặt khác nhau; một homography không mô tả đúng toàn bộ máy 3D. Tỷ lệ đích phải phù hợp bề mặt; nếu thiếu thông tin hình học hoặc mặt bị che/cắt, ghi rõ giới hạn và không coi số đo là toàn máy.

`example_integration.py` có ví dụ `create_engine`, `analyze_original` và `rectify_masks`. Các hàm này không tự tạo H, không chạy detector và chưa chấm mức độ.

## 6. Kiểm tra trước khi nối UI

Từ thư mục có `smoke_test.py`, chọn ảnh nguồn và mask segmentation của chính ảnh đó, đều ở tọa độ gốc đúng hướng. Các đường dẫn dưới đây là ví dụ; thay bằng file thật của đồ án:

```powershell
python smoke_test.py --image "C:\duong-dan\anh.png" --body "C:\duong-dan\phone_mask.png" --out "ket_qua_thu_01" --device cpu
```

Đầu ra gồm mask PNG, overlay PNG và result.json. Thư mục kết quả phải chưa tồn tại. Script không cần phone_detect checkpoint vì bạn đã cấp mask.

Kiểm tra mask khớp vị trí ảnh, overlay cùng chiều, detector_loaded=false, threshold=0.4, inference_variant=native. Thử thêm ảnh không phát hiện điện thoại và mask sai kích thước để bảo đảm app báo lỗi đúng.

Gói có `verification.json` ghi kiểm tra tương đương engine nguồn trên một ảnh validation bằng cùng RGB/mask. Đây là kiểm tra đóng gói, không phải phép đánh giá chất lượng mới hoặc bảo đảm tốc độ máy đích.

## 7. Nếu đồ án không dùng Python trực tiếp

Nếu giao diện là Flutter, C#, JavaScript hoặc ngôn ngữ khác, giữ model trong Python service/worker và nối API theo kiến trúc sẵn có. Truyền ảnh gốc và mask đúng tọa độ, trả JSON số đo cùng mask/overlay PNG. Không cố mở checkpoint này trực tiếp bằng runtime khác. Chỉ cân nhắc ONNX/TorchScript sau một bước export và kiểm tra sai lệch riêng; gói này chưa có bản export đó.

## 8. Bước đánh giá mức độ

Chưa được cài trong gói. Dùng `PROMPT_TICH_HOP_VA_DANH_GIA.md` để giao AI trong đồ án tích hợp và viết tầng hình học tạm thời. Tầng này không cần train lại; mọi ngưỡng severity là cấu hình thử nghiệm, tách khỏi threshold phát hiện 0,4 và báo ảnh 200 pixel.
