# import os
# BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "data", "app.db")
# SECRET_KEY = "dev-key-please-change"

# # --- Firebase config ---
# FIREBASE_SERVICE_ACCOUNT = os.path.join(BASE_DIR, "firebase_config.json")
# FIREBASE_API_KEY = "AIzaSyAc50uDUKyldmZ-oDXOrUbBt87fjNJhzEI"   # ✅ API key thật của bạn
# USE_FIREBASE = True   # ✅ bật dùng Firebase thật
import os

# ----------------------------
# CONFIG CHO FLASK + FIREBASE
# ----------------------------

# Khóa bí mật Flask (dùng cho session, flash)
SECRET_KEY = os.environ.get("SECRET_KEY", "mysecretkey")

# --- Firebase ---
# True: dùng Firebase
# False: fallback sang CSV để chạy offline
USE_FIREBASE = True   # ⚠️ Nếu bạn chỉ test local, có thể tạm để False

# File JSON Service Account (đã tải từ Firebase Console)
FIREBASE_SERVICE_ACCOUNT = os.path.join(os.getcwd(), "firebase_config.json")

# Firebase Web API key (lấy trong phần Project Settings -> General -> Web API Key)
# Nếu chưa có, tạm để chuỗi rỗng "" hoặc "<API_KEY>"
FIREBASE_API_KEY = "AIzaSyAc50uDUKyldmZ-oDXOrUbBt87fjNJhzEI"

# Collection trong Firestore
FIREBASE_COLLECTION_USERS = "users"
FIREBASE_COLLECTION_DATA = "weather_yield"

# ----------------------------
# DỮ LIỆU LOCAL
# ----------------------------
BASE_DIR = os.getcwd()

# Thư mục chứa dữ liệu (NASA, FAO, CSV người dùng)
DATA_PATH = os.path.join(BASE_DIR, "data", "nasa_data")

# File CSV dùng cho fallback (nếu không dùng Firebase)
USERS_CSV = os.path.join(BASE_DIR, "data", "users.csv")
SEASONS_CSV = os.path.join(BASE_DIR, "data", "seasons.csv")

# File thời tiết (NASA)
WEATHER_CSV = os.path.join(BASE_DIR, "data", "nasa_data", "weather_all_vn_annual.csv")

# File mô hình dự báo năng suất (train_predict_yield.py sinh ra)
MODEL_PATH = os.path.join(BASE_DIR, "data", "yield_model.pkl")

# ----------------------------
# KHÁC
# ----------------------------
# Tùy chọn port (nếu muốn đổi khi deploy)
PORT = int(os.environ.get("PORT", 5000))

