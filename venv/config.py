# import os
# BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "data", "app.db")
# SECRET_KEY = "dev-key-please-change"

# # --- Firebase config ---
# FIREBASE_SERVICE_ACCOUNT = os.path.join(BASE_DIR, "firebase_config.json")
# FIREBASE_API_KEY = "AIzaSyApTLuUgUm5lFTv3pdmqqbxaoX48fo9Dv4"   # ✅ API key thật của bạn
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
FIREBASE_API_KEY = "AIzaSyA5osaLKa3YA4sjojAUaK2FmF_TkYVr8aU"

# Collection trong Firestore
FIREBASE_COLLECTION_USERS = "users"
FIREBASE_COLLECTION_DATA = "weather_yield"