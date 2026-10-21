# Prompt giao AI trong đồ án

Bạn đang làm việc trong repository ứng dụng xử lý ảnh và phát hiện hư hại ngoại quan điện thoại của tôi. Hãy đọc cấu trúc dự án, hướng dẫn repository và luồng xử lý ảnh hiện có, sau đó tích hợp phone damage v3 cùng tầng đánh giá mức độ bằng hình học. Thực hiện code và kiểm tra trong repository này, không chỉ trả lời kế hoạch. Giữ quy ước kiến trúc/UI của ứng dụng.

## Phạm vi đã chốt

- Không train thêm model, không đổi checkpoint hoặc tự đổi thông số suy luận v3.
- Ứng dụng đã dùng phone_detect để segmentation và lấy bốn góc chỉnh phối cảnh. Dùng lại kết quả đó, không nạp/chạy detector thứ hai cho cùng ảnh.
- Severity chỉ là đánh giá tạm thời theo hình học của mask, chưa phân biệt chắc chắn xước/nứt/móp và chưa được hiệu chỉnh bằng nhãn mức độ của con người.
- Giữ UI gọi kết quả là “Mức độ hư hại ước tính”. Không suy ra độ sâu vật liệu, chức năng cảm ứng/camera, chi phí hoặc độ lành toàn thiết bị.
- Chưa cần mô hình phân loại mới, hệ thống gán nhãn hoặc điểm số 0–100.

## Tài nguyên bàn giao

Tôi đã copy gói `phone_damage_v3_kit` hoặc thư mục con `phone_damage_v3` vào đồ án. Tìm vị trí thực tế, đọc README_VI.md, example_integration.py, protocol.json và verification.json nếu có. Không giả định đồ án tồn tại ở D:\trainModel.

Thư mục package có __init__.py, damage_roi_engine.py, damage_roi_inference.py, phone_body_roi.py, phone_damage_roi.py, phone_semantic.py, phone_data.py, train_damage_roi.py và weights/model.pt + weights/protocol.json. Các module dùng import tương đối. train_damage_roi.py cung cấp load_model và không chạy train khi import; không xóa nó chỉ vì tên file.

Đây là checkpoint PyTorch kiến trúc `resnet18_unet_phone_context_v3`, không phải YOLO/TorchScript. phone_detect của pipeline đã kiểm chứng là RF-DETR SegSmall. Dùng loader có sẵn, không dùng YOLO(model.pt), torch.jit.load hoặc tự dựng mạng khác.

## A. Tích hợp model

1. Xác định backend Python/worker và nơi ứng dụng đang chạy phone_detect, chuẩn hóa EXIF, resize/letterbox và chỉnh phối cảnh. Nếu frontend dùng ngôn ngữ khác, nối vào Python backend theo kiến trúc sẵn có; chưa chuyển checkpoint sang runtime khác.
2. Kiểm tra torch/torchvision tương thích trước khi bổ sung thư viện. requirements-inference.txt không cài cặp này vì phải giữ lựa chọn CPU/CUDA phù hợp. environment-tested.json chỉ ghi môi trường đã chạy ở máy nguồn. Không làm thay đổi môi trường đang hoạt động nếu không cần.
3. Nạp một ROIDamageEngine khi worker khởi động:

   `engine = ROIDamageEngine(weights_dir, load_phone_detector=False, device=chosen_device)`

   Tính weights_dir từ cấu hình hoặc vị trí package, không hardcode đường dẫn máy nguồn. Không khởi tạo lại mỗi request. Kiểm tra SHA256 phone detector hiện có với engine.phone_model_sha256. Không âm thầm bỏ kiểm tra hash checkpoint/protocol.
4. Chuẩn hóa hướng ảnh trước detector và damage. Đầu vào RGB gốc chưa warp, numpy.uint8 H×W×3, 0–255. OpenCV BGR phải chuyển RGB. Giữ độ phân giải nguồn; engine đã tự chia patch/context.
5. Mask điện thoại phải là segmentation thật, bool hoặc int 0/1/255, H×W cùng tọa độ ảnh gốc. Quy đổi ngược resize/letterbox và giữ đúng một máy mục tiêu. Bốn góc, bounding box và probability map không thay thế trực tiếp mask.
6. Gọi `damage_mask, candidate_pixels = engine.predict_with_body(rgb_original, phone_mask_original)`. damage_mask là bool H×W ở ảnh gốc. Giữ threshold=0.4, patch=512, overlap=128, context=512, body_margin=0, inference_variant=native theo protocol; không thêm bước chuẩn hóa ảnh làm thay đổi đầu vào.
7. Giữ cờ `found = candidate_pixels >= engine.alarm_pixels` (mặc định 200) ở ảnh gốc. Đây là cờ báo có ứng viên theo quy ước hiện tại, tách khỏi severity. Không xóa các ứng viên chỉ vì tổng dưới 200.
8. Áp cùng H và kích thước đích của RGB chỉnh phối cảnh lên damage mask và mask bề mặt quan sát, dùng INTER_NEAREST cho mask. Không đưa ảnh đã nắn trực tiếp vào checkpoint hiện tại để thay luồng trên.
9. Phân biệt PhoneNotFound, lỗi mask/tọa độ, lỗi model và không có ứng viên. Không biến ngoại lệ thành “máy không hỏng”. Lưu/truyền mask bằng PNG 0/255 hoặc mảng nhị phân, không JPEG. Trả JSON số đo và đường dẫn/ID tài nguyên mask/overlay theo cách app sẵn có; không serialize trực tiếp numpy array.

## B. Tầng hình học, không train

Viết module độc lập, ví dụ damage_severity.py, không thay đổi mask gốc dùng overlay hoặc suy luận. Đầu vào gồm damage mask, mask bề mặt quan sát cùng hệ tọa độ, thông tin chỉnh phối cảnh/kích thước mặt và chất lượng quan sát mà app thực sự biết.

Chỉ chấm cho từng mặt gần phẳng. Không dùng một H cho cả mặt trước và cạnh cong. Cần tỷ lệ khung đích hợp lý; nếu không có H đáng tin cậy hoặc chỉ thấy một phần mặt, trả thông số giới hạn cùng needs_review, không báo phần trăm hỏng toàn máy. Không suy ra tỷ lệ nhìn thấy hoặc chất lượng bằng số tự bịa.

Trên mặt đã chuẩn hóa, tính D = damage AND visible_surface. Nếu thiếu/không có surface thì báo insufficient_evidence. Định nghĩa các đại lượng tỷ lệ trong [0,1] hoặc tỷ lệ có thể vượt 1 với chiều dài mạng phân nhánh; ghi rõ đơn vị:

- A = số pixel D / số pixel visible_surface. Đây là tỷ lệ vùng ứng viên trên mặt quan sát.
- Tách vùng liên thông trên D để phân tích; số vùng không được diễn giải là số vết vật lý.
- Skeleton/medial axis cho mỗi vùng. Ước lượng chiều dài skeleton bằng tổng cạnh graph lân cận với độ dài ngang/dọc=1 và chéo=sqrt(2), đếm mỗi cạnh một lần và có quy ước tránh cộng đường chéo dư ở các góc bậc thang. Báo đây là chiều dài skeleton xấp xỉ, không phải chiều dài thật của vết nứt đã xác nhận.
- L = chiều dài skeleton lớn nhất trong các vùng / đường chéo của toàn mặt chuẩn hóa. Một điểm skeleton đơn lẻ có chiều dài bằng 0, không NaN. Lưu thêm tổng chiều dài để mô tả nhưng không thay L âm thầm.
- Khoảng cách tới biên D dùng distance transform; bề rộng mask xấp xỉ bằng 2×distance tại skeleton. Pad biên phù hợp để xử lý cả mask sát/full khung. Với mỗi vùng lấy percentile 90 của bề rộng skeleton, rồi W = giá trị lớn nhất trong các vùng / cạnh ngắn của toàn mặt chuẩn hóa. Xử lý skeleton rỗng an toàn. Không gọi W là độ sâu hoặc kích thước mm.
- Mẫu số chiều dài/bề rộng lấy kích thước toàn mặt có hình học xác định, không lấy bounding box của từng vết hoặc tự suy ra từ phần mặt còn sót lại do bị che.

Không dilation/closing để làm vết to hơn trước khi đo rồi coi đó là vùng thật. Nếu cần mask xử lý riêng để skeletonize, lưu rõ quy trình và không thay mask nguồn. Không tự lọc mất các vết mảnh chỉ vì diện tích nhỏ; mọi quy tắc loại nhiễu phải cấu hình và có kiểm tra ảnh hưởng riêng.

## C. Quy tắc thử nghiệm có cấu hình

Để chạy bản đầu không cần thêm thao tác gán nhãn, dùng các giá trị khởi tạo dưới đây, ghi rõ là heuristic chưa kiểm chứng, không phải chuẩn grading điện thoại:

- Area A: moderate từ 0.005 (0,5%), severe từ 0.03 (3%).
- Length L: moderate từ 0.20 đường chéo, severe từ 0.50 đường chéo.
- Width W: moderate từ 0.005 cạnh ngắn, severe từ 0.015 cạnh ngắn.

Tách tất cả ngưỡng ra JSON/config có phiên bản; giá trị nội bộ là tỷ lệ, UI mới đổi sang %. Kiểm tra 0 <= moderate < severe và số hữu hạn. Không khẳng định các giá trị này tối ưu hoặc đã được kiểm chứng. Đừng thay threshold phát hiện 0.4 hoặc ngưỡng 200 pixel bằng các ngưỡng này.

Mỗi chỉ số trả 1=minor, 2=moderate, 3=severe khi có ứng viên; lấy mức cao nhất của ba chỉ số, lưu lý do chỉ số nào kích hoạt. Không chỉ xét L/W sau nhánh A nhỏ, và không lấy trung bình khiến vết dài mảnh bị hạ cấp. Không áp trọng số camera/màn hình khi chưa biết đúng bộ phận.

- Nếu D rỗng: estimated_severity=null, trạng thái no_detected_damage trong mặt quan sát; không ghi máy hoàn toàn lành.
- Nếu hình học/ảnh không đủ: insufficient_evidence hoặc needs_review. Có thể giữ số đo mang tính mô tả, không xuất phân cấp chính thức.
- Nếu có ứng viên nhưng found=false theo ngưỡng 200: giữ riêng hai kết quả, ghi below_alarm_threshold/needs_review để UI không diễn giải mâu thuẫn; không âm thầm biến mask thành rỗng.
- Mọi phân cấp đều mang cờ heuristic_unvalidated. Chỉ chấm theo mặt được quan sát, không cộng diện tích trùng nhau từ nhiều ảnh.

## D. API/UI và kiểm tra

JSON nên có: trạng thái phát hiện, candidate_pixels_original, found, threshold, mặt quan sát, hệ tọa độ đo, area_ratio, skeleton_length_ratio, width_ratio, estimated_severity, reasons, needs_review và phiên bản cấu hình. Với số đo không có, dùng null; không dùng 0 để che lỗi. Các giá trị phải serialize hợp lệ, không NaN/Inf. UI hiển thị mask, số đo với đơn vị, “Mức độ hư hại ước tính” và ghi chú phương pháp dựa trên hình học.

Kiểm tra có ý nghĩa:

- Đường mảnh dài có A nhỏ vẫn tăng cấp theo L; đốm ngắn dày có thể tăng theo W; mảng rộng tăng theo A.
- Mask rỗng, surface rỗng, một pixel, full mask, sát biên, nhiều vùng, vòng kín; không lỗi/NaN.
- Resize đồng dạng của cùng bề mặt cho chỉ số chuẩn hóa và phân cấp gần nhau, trong sai số raster hóa đã giải thích. Chỉ số không đổi chỉ vì độ phân giải tăng.
- Ảnh BGR/RGB, EXIF, phép warp và mask/ảnh phải khớp; thử input sai kích thước và không tìm thấy điện thoại.
- So sánh suy luận trước/sau tích hợp trên cùng ảnh và cùng body mask, yêu cầu mask tương đương chính xác khi cùng môi trường/protocol. Gói có smoke_test.py để thử độc lập.
- Model/detector chỉ được nạp một lần theo worker và detector không chạy lại trong damage stage. Xử lý an toàn yêu cầu đồng thời theo kiến trúc app.
- Không chọn ngưỡng bằng tập test đã công bố, không báo accuracy severity khi chưa có nhãn. Chỉ báo kiểm thử thuật toán và ví dụ thực tế đã chạy.

Hoàn tất code, nối backend/UI theo phạm vi có thể xác định trong repo và chạy kiểm tra phù hợp. Báo các file thay đổi, cách chạy, API mẫu, kết quả kiểm tra và giới hạn còn lại. Nếu thiếu model/gói hoặc không tìm thấy luồng phone_detect, xác định chính xác tài nguyên còn thiếu; không giả tạo kết quả model để coi như tích hợp thành công.
