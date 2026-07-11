# BÁO CÁO TỔNG KẾT: CHUYỂN DỊCH HỆ THỐNG TWITTER DATA LAKEHOUSE LÊN AWS
## Từ Mô Hình Local Docker Compose Sang Kiến Trúc AWS Cloud-Native Serverless

---

## 📋 1. TỔNG QUAN & BỐI CẢNH DỰ ÁN

Dự án **Twitter Data Lakehouse** được xây dựng nhằm thu thập, lưu trữ, xử lý chất lượng và phân tích dữ liệu Twitter theo thời gian thực hoặc định kỳ. 

### Quá trình phát triển trải qua 2 cột mốc chính:
1.  **Giai đoạn 1 (Local Development)**: Triển khai trên môi trường giả lập sử dụng **Docker Compose** trên một máy chủ ảo EC2 cấu hình thấp (t3.micro - 1GB RAM) với các công cụ mã nguồn mở tự host (Airflow, MinIO, Apache Drill, Superset, PostgreSQL).
2.  **Giai đoạn 2 (Production Migration)**: Dịch chuyển hoàn toàn hạ tầng lên môi trường Cloud-Native của **AWS**, chuyển đổi các phần mềm tự host sang dịch vụ **Serverless & Fully Managed** để tối ưu hóa chi phí vận hành, bảo mật và khả năng mở rộng quy mô.

---

## 🗺️ 2. BẢN ĐỒ BIẾN ĐỔI KIẾN TRÚC (ARCHITECTURE EVOLUTION MAP)

Dưới đây là bảng đối chiếu chi tiết sự thay đổi của các thành phần hệ thống từ lúc bắt đầu cho đến khi triển khai thành công lên AWS:

| Thành phần | Giai đoạn 1: Local Docker Stack | Giai đoạn 2: AWS Serverless Stack | Lý do chuyển đổi & Ưu điểm vượt trội |
| :--- | :--- | :--- | :--- |
| **Storage Layer** | **MinIO** (Self-hosted container) | **Amazon S3** (Simple Storage Service) | Durability 99.999999999%, tự động co giãn dung lượng không giới hạn, không cần quản trị ổ đĩa. |
| **Ingestion** | `generate_twitter_data` (Airflow Task) | **AWS Lambda** (Python 3.9) | Khởi chạy serverless tức thì qua lịch **EventBridge**, tự động tắt khi chạy xong, chi phí chạy gần như $0. |
| **Processing / ETL** | Airflow Task (Pandas local) | **AWS Lambda** + **AWSSDKPandas Layer** | Thực hiện flatten, transform và xuất Parquet nén Snappy trực tiếp từ Lambda. Tận dụng lớp thư viện tối ưu của AWS. |
| **Metadata Catalog** | Drill Storage Plugin configuration | **AWS Glue Data Catalog** + **Glue Crawler** | Tự động quét phân vùng thư mục S3, suy luận kiểu dữ liệu tự động, loại bỏ bước định nghĩa schema thủ công. |
| **Compute / SQL Query** | **Apache Drill** (Tốn RAM cố định) | **Amazon Athena** (Presto/Trino Serverless) | Không tốn tài nguyên chạy idle. Tự động phân phối hàng trăm node tính toán song song, chỉ trả tiền trên dung lượng quét ($5/TB). |
| **Orchestration** | **Apache Airflow** (Local Docker) | **AWS Step Functions** | Loại bỏ hoàn toàn Airflow Scheduler & Metadata DB để tiết kiệm chi phí MWAA (~$350/tháng). Điều phối kéo thả trực quan, tự phục hồi và cảnh báo lỗi qua SNS. |
| **BI / Presentation** | **Apache Superset** (Tự host) | **Amazon QuickSight** (Enterprise) | BI Serverless kết nối trực tiếp Athena. Sử dụng bộ nhớ đệm **SPICE** tăng tốc render biểu đồ và giảm 99% chi phí truy vấn Athena. |
| **Database phụ trợ** | **PostgreSQL** (Docker container) | **Không cần sử dụng** | Nhờ chuyển dịch sang Step Functions & Athena, chúng ta không cần duy trì bất kỳ cơ sở dữ liệu quan hệ nào cho metadata. |

---

## 🛠️ 3. CHI TIẾT CÁC THAY ĐỔI VỀ MÃ NGUỒN & HẠ TẦNG

Để thực hiện dịch chuyển này, toàn bộ cấu hình hạ tầng và logic xử lý đã được viết lại sang định dạng Cloud-Native:

### 3.1. Chuyển đổi mã nguồn ETL (Airflow DAG ➔ AWS Lambda)
*   **Trước đây**: Logic ETL được đóng gói trong một file Airflow DAG duy nhất (`twitter_etl.py`) với các task tuần tự.
*   **Hiện tại**: Được chia làm 2 hàm Lambda độc lập lưu tại thư mục [app/lambda/](file:///d:/AllCourse/DienToanDamMay/deTaiDientoanDammay/twitter-data-lakehouse/app/lambda/):
    1.  [lambda_ingest.py](file:///d:/AllCourse/DienToanDamMay/deTaiDientoanDammay/twitter-data-lakehouse/app/lambda/lambda_ingest.py): Nhận mock tweets, xác thực qua Pydantic schema [models.py](file:///d:/AllCourse/DienToanDamMay/deTaiDientoanDammay/twitter-data-lakehouse/app/lambda/models.py) và ghi JSON thô vào thư mục `raw/` trên S3.
    2.  [lambda_process.py](file:///d:/AllCourse/DienToanDamMay/deTaiDientoanDammay/twitter-data-lakehouse/app/lambda/lambda_process.py): Đọc JSON từ S3, dọn dẹp và flatten dữ liệu, chuyển đổi sang Parquet nén Snappy bằng Pandas/PyArrow và ghi vào thư mục phân vùng ngày tháng `processed/` trên S3.

### 3.2. Cấu hình Hạ tầng dưới dạng Code (Docker Compose ➔ Terraform)
*   **Trước đây**: Hệ thống được chạy bằng file cấu hình container [docker-compose.yaml](file:///d:/AllCourse/DienToanDamMay/deTaiDientoanDammay/twitter-data-lakehouse/docker-compose.yaml).
*   **Hiện tại**: Được định nghĩa bằng tệp hạ tầng dạng code Terraform [main.tf](file:///d:/AllCourse/DienToanDamMay/deTaiDientoanDammay/twitter-data-lakehouse/scripts/terraform/main.tf) và [variables.tf](file:///d:/AllCourse/DienToanDamMay/deTaiDientoanDammay/twitter-data-lakehouse/scripts/terraform/variables.tf). Chỉ cần gõ lệnh chạy, Terraform sẽ tự động khởi tạo S3, Glue Database, IAM Roles, Lambda, Step Functions, và EventBridge.

### 3.3. Dịch chuyển Quy trình Điều phối (Airflow Scheduler ➔ AWS Step Functions)
*   **Trước đây**: Lập lịch và bắt lỗi thông qua cấu hình trong Airflow DAG.
*   **Hiện tại**: Sử dụng State Machine định nghĩa bằng định dạng JSON [step_function.json](file:///d:/AllCourse/DienToanDamMay/deTaiDientoanDammay/twitter-data-lakehouse/scripts/step_functions/step_function.json). Quá trình chạy có giao diện giám sát trực quan bằng màu sắc trên AWS Console và hỗ trợ cơ chế tự động thử lại (Retry) và thông báo lỗi.

### 3.4. Chuyển đổi Câu lệnh SQL (Apache Drill ➔ AWS Athena)
*   **Trước đây**: Các truy vấn phân tích được viết trên Apache Drill SQL, trỏ trực tiếp vào đường dẫn vật lý của MinIO (`s3.root.`tweets/*/*/*/*.parquet``).
*   **Hiện tại**: Viết lại hoàn toàn trong file [athena_queries.sql](file:///d:/AllCourse/DienToanDamMay/deTaiDientoanDammay/twitter-data-lakehouse/app/athena_queries.sql) tương thích với engine Athena, truy vấn thông qua các bảng logic trong Glue Catalog (ví dụ: `twitter_lakehouse.processed`).

---

## 💎 4. ĐÁNH GIÁ HIỆU QUẢ SAU DỊCH CHUYỂN

### 1. Tối ưu hóa chi phí (Cost-Efficiency)
*   **Local/Docker EC2**: Tốn chi phí cố định tối thiểu **$8 - $15/tháng** để duy trì máy chủ chạy 24/7 (dù không có dữ liệu mới).
*   **AWS Serverless**: Phí tính hoàn toàn theo lượng sử dụng thực tế. Với chu kỳ chạy 6 tiếng/lần, chi phí thực tế ước tính **<$0.05/tháng** (Nằm hoàn toàn trong gói **AWS Free Tier** và bảo toàn tuyệt đối gói credit **$120** của bạn).

### 2. Khả năng mở rộng (Scalability)
*   **Trước đây**: Drill và Superset chạy trên t3.micro (1GB RAM) rất dễ bị treo hoặc OOM (Out Of Memory) nếu xử lý trên 10,000 tweets.
*   **Hiện tại**: S3 và Athena có khả năng xử lý đồng thời hàng tỷ bản ghi dữ liệu (quy mô Big Data thực tế) mà không cần can thiệp nâng cấp cấu hình máy chủ.

### 3. Tính bảo mật (Enterprise Security)
*   **Trước đây**: Sử dụng mật khẩu root cố định lưu trong file `.env` dễ bị rò rỉ.
*   **Hiện tại**: Không dùng mật khẩu cứng. Các dịch vụ kết nối với nhau thông qua **AWS IAM Roles** với cơ chế bảo mật xác thực ngắn hạn theo nguyên tắc quyền hạn tối thiểu.

---

## 🚀 5. HƯỚNG DẪN TRIỂN KHAI CHO NGƯỜI DÙNG CUỐI

Quy trình cài đặt chi tiết và hướng dẫn triển khai thực tế bằng dòng lệnh đã được biên soạn đầy đủ tại tệp tài liệu:
📂 **[aws_deployment_guide.md](file:///d:/AllCourse/DienToanDamMay/deTaiDientoanDammay/twitter-data-lakehouse./aws_deployment_guide.md)**
