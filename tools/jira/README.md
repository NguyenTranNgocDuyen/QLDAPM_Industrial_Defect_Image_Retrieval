# Công Cụ Đồng Bộ Kế Hoạch Dự Án Lên Jira Cloud (`tools/jira`)

Bộ script Python thuần thư viện chuẩn (không cần `pip install`) giúp tạo tự động toàn bộ cấu trúc quản trị Scrum trên Jira Cloud dưới tài khoản của chính bạn:

- **6 Epics:** 5 Epic Active (Phone Defect + Khung mở rộng không train) + **Epic 6 (`ON HOLD` — Train Keyboard, `Unassigned`)**.
- **5 Sprints:** Từ `09/09/2026` đến `18/11/2026` (khớp lịch sử Git thực tế) kèm `Sprint Goal`.
- **45 Active Issues** ở trạng thái **`To Do`** (phân bổ cho `TV1`–`TV5`) + **4 On-Hold Issues** (`Unassigned`, nằm ngoài Sprint).
- **Gắn Remote Web Links GitHub chính thức** (có icon GitHub) trỏ trực tiếp tới từng Commit, Pull Request (`#1`, `#2`, `#4`) và file mã nguồn/tài liệu thật trong repository.
- **Chống tạo trùng (Idempotent):** Chạy lại nhiều lần sẽ tự bỏ qua issue đã tạo và chỉ cập nhật Web Links / Sprint.
- **Tự xuất Checklist cho 5 thành viên** tại `outputs/jira_member_checklists.md` kèm link bấm trực tiếp tới từng thẻ Jira.

---

## Hướng dẫn chạy (5 bước)

### Bước 1 — Chuẩn bị trên Jira Cloud
1. Tạo 1 Project mới theo template **Scrum** (đặt Key ví dụ: `IDIR`).
2. Vào **Project Settings → Access → Add people**, mời đủ 4 thành viên còn lại bằng email và chờ cả 5 người Accept lời mời.
3. *(Tùy chọn)* Thêm trạng thái **`On Hold`** trong Workflow của Project để Epic 6 và 4 task Train Keyboard tự động chuyển sang `On Hold`.
4. Tạo **Atlassian API Token** của bạn tại: `https://id.atlassian.com/manage-profile/security/api-tokens`.

### Bước 2 — Tạo file cấu hình `.env.jira` (cục bộ, không commit)
Tại thư mục gốc repository:

```powershell
Copy-Item tools/jira/jira_env.example .env.jira
```

Mở `.env.jira` và điền `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`.
*(File `.env.jira` đã được `.gitignore` chặn tự động).*

### Bước 3 — Kiểm tra kết nối & lấy `accountId` / email 5 thành viên
```powershell
python tools/jira/sync_jira_project.py --check-connection
```

Lệnh này sẽ xác nhận quyền truy cập, tự phát hiện Scrum Board / Custom Fields (`Story Points`, `Start date`) và in danh sách thành viên trong Project. Copy `accountId` (hoặc email) của 5 bạn điền vào `TV1_USER` → `TV5_USER` trong `.env.jira`, rồi chạy lại `--check-connection` để thấy cả 5 dòng báo `OK`.

### Bước 4 — Chạy thử (`--dry-run`)
```powershell
python tools/jira/sync_jira_project.py --dry-run
```

### Bước 5 — Đẩy toàn bộ lên Jira thật
```powershell
python tools/jira/sync_jira_project.py
```

Sau khi chạy xong:
1. Mở file `outputs/jira_member_checklists.md` vừa được tạo (có sẵn link từng thẻ Jira cho `TV1`–`TV5`).
2. PM bấm **Start Sprint 1** (`09/09/2026` – `22/09/2026`), gửi checklist để 5 thành viên tự đăng nhập kéo thẻ của mình qua `In Progress` → `In Review` → `Done` và bình luận bằng chứng, rồi bấm **Complete Sprint 1** — lặp lại đến hết Sprint 5.

---

## Chế độ chỉ chạy phần của riêng mình (không đụng thẻ người khác)

Xem quy trình phối hợp đầy đủ của nhóm tại [`docs/JIRA_WORKFLOW_AND_PLAN.md`](../../docs/JIRA_WORKFLOW_AND_PLAN.md).

- **Chỉ xem trước / đồng bộ riêng các thẻ của bạn** (ví dụ bạn là `TV2`):
  ```powershell
  python tools/jira/sync_jira_project.py --only-role TV2 --dry-run
  python tools/jira/sync_jira_project.py --only-role TV2
  ```
- **Chỉ tự động kéo trạng thái (`In Progress` → `In Review` → `Done`) và đăng bình luận bằng chứng GitHub cho RIÊNG các thẻ được gán cho tài khoản của bạn** (có cơ chế tự kiểm tra `assignee == tài khoản đang đăng nhập`, tuyệt đối bỏ qua thẻ của người khác):
  ```powershell
  # Xem trước
  python tools/jira/sync_jira_project.py --complete-my-tasks --only-role TV2 --sprint S1 --dry-run
  # Chạy thật cho Sprint 1 của riêng bạn
  python tools/jira/sync_jira_project.py --complete-my-tasks --only-role TV2 --sprint S1
  ```
