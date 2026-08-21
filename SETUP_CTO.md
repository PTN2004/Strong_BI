# Hướng Dẫn Khởi Chạy Dự Án Strong BI (1-Click Deployment)

Chào sếp, dự án Strong BI đã được cấu hình tự động hoá hoàn toàn 100%. Sếp không cần phải thao tác thủ công, thiết lập cơ sở dữ liệu hay cấu hình `.env` phức tạp. Mọi thứ đã được đóng gói thành kịch bản "1-Click".

## 1. Yêu Cầu Hệ Thống
Trước khi chạy, sếp chỉ cần đảm bảo máy tính đã cài đặt:
- **Docker** & **Docker Compose** (Dùng để chạy hệ thống cơ sở dữ liệu như Neo4j, Postgres, FalkorDB).
- **Node.js** & **npm** (Dành cho Frontend).
- **Python 3.10+** và công cụ **uv** (Dành cho Backend, nếu chưa có `uv`, máy sẽ tự động cài bằng `pip`).

## 2. Cách Chạy Hệ Thống
Chỉ với 1 lệnh duy nhất ở thư mục gốc của dự án:

```bash
./start.sh
```

**Kịch bản tự động sẽ làm những việc sau:**
1. **Tạo Cấu Hình**: Tự động sinh file `.env` từ `.env.cto` (hoặc `.env.example`).
2. **Khởi Tạo CSDL**: Kích hoạt Docker Compose để dựng Postgres, Neo4j và FalkorDB.
3. **Nạp Dữ Liệu (Seed Data)**: Tự động khôi phục (restore) toàn bộ dữ liệu cấu trúc Schema (từ thư mục `db-seed/` chứa các file `.dump` và `.sql`) vào Neo4j và Postgres. Dữ liệu của dự án sẽ có sẵn để sếp trải nghiệm ngay.
4. **Cài Đặt Backend & Frontend**: Tự động tạo môi trường ảo Python (virtual environment), cài đặt các gói cần thiết bằng `uv`, cài đặt gói npm cho thư mục `app/`.
5. **Chạy Server**: Khởi chạy API Backend ở cổng **5000** và React Frontend ở cổng **5173**.

## 3. Truy Cập Hệ Thống
Sau khi lệnh trên chạy xong, sếp mở trình duyệt và truy cập vào:
- **Giao diện chính (Frontend)**: [http://localhost:5173](http://localhost:5173)
- **Backend API Docs**: [http://localhost:5000/docs](http://localhost:5000/docs)

*(Nhấn `Ctrl+C` ở màn hình Terminal đang chạy script để dừng toàn bộ hệ thống).*

## 4. Dành Cho Developer (Cập Nhật Data)
Nếu có sự thay đổi về cấu trúc Graph hoặc dữ liệu, dev chỉ cần chạy file:
```bash
./export_data.sh
```
Hệ thống sẽ kết xuất tự động mọi dữ liệu hiện tại trong Docker ra thư mục `db-seed/` để đẩy lên Github cho các bản cập nhật sau.

---
*Chúc sếp có trải nghiệm tuyệt vời với Strong BI!*
