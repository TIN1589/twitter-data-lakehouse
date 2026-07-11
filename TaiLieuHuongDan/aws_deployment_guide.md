# Hướng Dẫn Cài Đặt & Triển Khai Hạ Tầng AWS Serverless Bằng Terraform

Tài liệu này hướng dẫn chi tiết từng bước cách cài đặt Terraform trên Windows, cấu hình tài khoản AWS và thực hiện triển khai luồng xử lý dữ liệu **Twitter Data Lakehouse** hoàn chỉnh lên AWS.

---

## 📋 1. Chuẩn Bị Trước Khi Triển Khai (Prerequisites)

### Bước 1.1: Cấu hình thông tin đăng nhập AWS
Đảm bảo bạn đã cấu hình tài khoản AWS trên máy tính của mình thông qua lệnh:
```powershell
aws configure
```
Nhập các thông tin sau:
1. `AWS Access Key ID`
2. `AWS Secret Access Key`
3. `Default region name`: Nhập `ap-southeast-1` (Singapore) hoặc vùng bạn mong muốn.
4. `Default output format`: Nhấn Enter (để mặc định là `json`).

Để kiểm tra xem kết nối đến AWS đã hoạt động chưa, hãy chạy lệnh:
```powershell
aws sts get-caller-identity
```

---

## 🛠️ 2. Cài Đặt Terraform Trên Windows

Có 3 cách chính để cài đặt Terraform trên Windows. Bạn hãy chọn 1 trong 3 cách sau:

### Cách 1: Sử dụng Winget (Khuyên Dùng - Nhanh Nhất)
Mở PowerShell bằng quyền Admin (Run as Administrator) và chạy lệnh sau:
```powershell
winget install HashiCorp.Terraform
```
*Sau khi cài đặt xong, hãy đóng và mở lại cửa sổ PowerShell mới.*

### Cách 2: Sử dụng Chocolatey (Nếu máy bạn có sẵn Chocolatey)
Mở PowerShell Admin và chạy:
```powershell
choco install terraform
```

### Cách 3: Tải file Zip thủ công
1. Truy cập trang web chính thức của Terraform: [https://developer.hashicorp.com/terraform/downloads](https://developer.hashicorp.com/terraform/downloads)
2. Tải về bản **Windows 64-bit**.
3. Giải nén file tải về (bạn sẽ nhận được file `terraform.exe`).
4. Di chuyển file `terraform.exe` vào một thư mục cố định (ví dụ: `C:\terraform\`).
5. Thêm đường dẫn `C:\terraform\` vào biến môi trường **PATH** của hệ thống:
   * Tìm kiếm "Environment Variables" trong Menu Start.
   * Chọn **Environment Variables...**
   * Trong phần *System variables*, chọn dòng **Path** và nhấn **Edit...**
   * Nhấn **New** và dán đường dẫn `C:\terraform\` vào. Nhấn **OK** để lưu lại.

### Kiểm tra cài đặt thành công:
Mở một cửa sổ PowerShell mới và gõ lệnh:
```powershell
terraform -v
```
Nếu màn hình hiển thị phiên bản (ví dụ: `Terraform v1.x.x`), bạn đã cài đặt thành công.

---

## 🚀 3. Các Bước Triển Khai Lên AWS

Di chuyển terminal của bạn đến thư mục terraform trong dự án:
```powershell
cd scripts/terraform
```

### Bước 3.1: Khởi tạo Terraform (Init)
Tải về các plugin của nhà cung cấp AWS:
```powershell
terraform init
```

### Bước 3.2: Kiểm tra cấu hình & lập kế hoạch (Plan)
Xem trước các tài nguyên mà Terraform sẽ tạo ra trên tài khoản AWS của bạn:
```powershell
terraform plan
```
*Lưu ý: Lệnh này không thay đổi bất kỳ tài nguyên nào trên AWS, chỉ để kiểm tra trước.*

### Bước 3.3: Áp dụng triển khai (Apply)
Thực thi việc tạo lập các tài nguyên lên AWS:
```powershell
terraform apply
```
*Khi Terraform hỏi xác nhận `Do you want to perform these actions?`, hãy gõ `yes` và nhấn Enter.*

Quá trình này sẽ mất khoảng **1 - 3 phút**. Sau khi thành công, màn hình sẽ hiển thị trạng thái hoàn thành và xuất ra các thông tin đầu ra (S3 Bucket Name, Step Function ARN, v.v.).

---

## 🔍 4. Kiểm Thử Hệ Thống Trên AWS

### Bước 4.1: Chạy thử luồng xử lý dữ liệu
1. Truy cập vào **AWS Console** của bạn.
2. Tìm kiếm dịch vụ **Step Functions**.
3. Chọn State Machine có tên `twitter-lakehouse-pipeline`.
4. Nhấn nút **Start Execution** và giữ nguyên các tham số mặc định rồi nhấn **Start**.
5. Bạn sẽ thấy biểu đồ luồng chuyển sang màu xanh lá cây tương ứng với việc chạy thành công từng bước:
   * **Ingest**: Tạo mock data, xác thực qua Pydantic và ghi file JSON lên S3.
   * **Process**: Đọc JSON, chuyển đổi sang Parquet nén Snappy và lưu lại S3.
   * **Crawler**: Kích hoạt Glue Crawler cập nhật schema tự động.

### Bước 4.2: Truy vấn dữ liệu trên Amazon Athena
1. Vào dịch vụ **Amazon Athena** trên AWS Console.
2. Tại menu bên trái, phần Database, chọn database `twitter_lakehouse`.
3. Bạn sẽ thấy bảng `processed` xuất hiện.
4. Gõ câu lệnh SQL kiểm tra trong Query Editor:
   ```sql
   SELECT * FROM twitter_lakehouse.processed LIMIT 10;
   ```
5. Nhấn **Run** để xem kết quả trả về trực tiếp từ file Parquet lưu trên S3!

---

## 🧹 5. Dọn Dẹp Tài Nguyên (Tránh Phát Sinh Chi Phí)

Khi đã hoàn thành việc báo cáo/bảo vệ dự án, bạn nên xóa bỏ toàn bộ hạ tầng đã tạo để tránh việc phát sinh chi phí ngầm (dù là rất nhỏ):
```powershell
terraform destroy
```
*Gõ `yes` và nhấn Enter để xác nhận xóa toàn bộ tài nguyên.*
