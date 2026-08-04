import logging
import os

os.makedirs("logs", exist_ok=True)

# Tạo một logger chuyên dụng cho AI
ai_logger = logging.getLogger("AI_Agent_Logger")
ai_logger.setLevel(logging.INFO)

# Chống việc log bị in đúp ra màn hình console của hệ thống chính
ai_logger.propagate = False 

# Cấu hình ghi ra file (đảm bảo encoding utf-8 để không lỗi tiếng Việt/ký tự đặc biệt)
file_handler = logging.FileHandler("logs/ai_prompts.log", encoding="utf-8")
formatter = logging.Formatter('\n%(asctime)s - [%(name)s]\n%(message)s\n' + '='*80)
file_handler.setFormatter(formatter)

# Gắn handler vào logger (chỉ add nếu chưa có để tránh duplicate log)
if not ai_logger.handlers:
    ai_logger.addHandler(file_handler)