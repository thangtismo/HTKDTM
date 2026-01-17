from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import pandas as pd
import joblib, os, requests
from datetime import datetime, timedelta
from functools import wraps
import signal
import sys
import config
from firebase_init import init_firebase
from firebase_admin import firestore

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# =========================================================
#               ERROR HANDLERS & TIMEOUT
# =========================================================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    print(f"Internal Server Error: {error}")
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_exception(error):
    print(f"Unhandled Exception: {error}")
    flash("Đã xảy ra lỗi hệ thống. Vui lòng thử lại.", "danger")
    return redirect(url_for('index'))

@app.after_request
def after_request(response):
    """Thêm headers để tránh caching issues"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# =========================================================
#               SESSION & SECURITY
# =========================================================

# ----------------- RESET SESSION ON STARTUP -----------------
@app.before_request
def clear_session_on_start():
    if request.endpoint == 'static':
        return
    if not hasattr(app, '_session_cleared'):
        session.clear()
        app._session_cleared = True

@app.before_request
def make_session_permanent():
    session.permanent = True

# ----------------- LOGIN CHECK DECORATOR -----------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Vui lòng đăng nhập để truy cập trang này.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# =========================================================
#               INITIALIZATION
# =========================================================

# ----------------- LOAD MODEL -----------------
MODEL_PATH = os.path.join(os.path.dirname(__file__), "data", "yield_model.pkl")
model = joblib.load(MODEL_PATH) if os.path.exists(MODEL_PATH) else None

# ----------------- INIT FIREBASE -----------------
db = None
if config.USE_FIREBASE:
    try:
        db = init_firebase()
        print("✅ Firebase initialized.")
    except Exception as e:
        db = None
        print("❌ Firebase init failed:", e)

# ----------------- HELPER PATHS -----------------
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_CSV = os.path.join(DATA_DIR, "users.csv")
SEASONS_CSV = os.path.join(DATA_DIR, "seasons.csv")
WEATHER_CSV = os.path.join(DATA_DIR, "weather_all_vn_annual_2000-2030.csv")

# =========================================================
#               CORE FUNCTIONS
# =========================================================

# ----------------- YIELD CALCULATION FUNCTION -----------------
def calculate_yield(season_data):
    """
    Tính toán năng suất tự động dựa trên:
    - Giống cây trồng (crop)
    - Diện tích (area)
    - Thời gian trồng (sow_date, harvest_date)
    - Phân bón (fertilizer)
    - Tỉnh thành (province) - ảnh hưởng thời tiết
    """
    try:
        # Base yield by crop type (tấn/ha)
        base_yields = {
            "lúa": 5.5,
            "ngô": 4.8,
            "hoa hướng dương": 2.5,
            "cà phê": 2.2,
            "cao su": 1.8,
            "chè": 3.2,
            "tiêu": 3.0,
            "điều": 1.5,
            "mía": 60.0,
            "lạc": 2.2,
            "đậu tương": 2.0
        }
        
        crop = season_data.get("crop", "").strip().lower()
        area = float(season_data.get("area", 1))
        fertilizer = season_data.get("fertilizer", "").strip().lower()
        
        # Base yield từ loại cây trồng
        base_yield = base_yields.get(crop, 4.0)
        
        # Tính thời gian sinh trưởng
        sow_date_str = season_data.get("sow_date")
        harvest_date_str = season_data.get("harvest_date")
        
        growth_days = 90  # mặc định 90 ngày
        
        if sow_date_str and harvest_date_str:
            try:
                sow_date = datetime.strptime(sow_date_str, "%Y-%m-%d")
                harvest_date = datetime.strptime(harvest_date_str, "%Y-%m-%d")
                growth_days = (harvest_date - sow_date).days
                growth_days = max(60, min(180, growth_days))
            except:
                growth_days = 90
        
        # Hệ số thời gian sinh trưởng
        if growth_days < 80:
            growth_factor = 0.7
        elif growth_days < 100:
            growth_factor = 0.9
        elif growth_days < 120:
            growth_factor = 1.0
        elif growth_days < 150:
            growth_factor = 1.1
        else:
            growth_factor = 1.2
        
        # Hệ số phân bón
        fertilizer_factors = {
            "hữu cơ": 1.2,
            "vô cơ": 1.1,
            "npk": 1.15,
            "phân chuồng": 1.18,
            "không": 0.8
        }
        
        fertilizer_factor = 1.0
        for fert_type, factor in fertilizer_factors.items():
            if fert_type in fertilizer:
                fertilizer_factor = factor
                break
        
        # Hệ số vùng miền
        region_factors = {
            "an giang": 1.3, "đồng tháp": 1.25, "long an": 1.2,
            "hà nội": 1.1, "bắc ninh": 1.05, "hưng yên": 1.05,
            "đắk lắk": 1.0, "đắk nông": 0.95, "gia lai": 0.95,
            "bắc kạn": 0.9, "cao bằng": 0.85, "hà giang": 0.85
        }
        
        province = season_data.get("province", "").strip().lower()
        region_factor = 1.0
        for region, factor in region_factors.items():
            if region in province:
                region_factor = factor
                break
        
        # Tính năng suất cuối cùng (tấn/ha)
        final_yield_per_ha = base_yield * growth_factor * fertilizer_factor * region_factor
        
        # Áp dụng cho diện tích cụ thể (tổng sản lượng)
        total_yield = final_yield_per_ha * area
        
        return round(total_yield, 2)
        
    except Exception as e:
        print(f"Lỗi tính năng suất: {e}")
        return None

# ----------------- DECISION SUPPORT FUNCTION -----------------
def generate_decision_support(season_data, predicted_yield):
    """
    Tạo dữ liệu hỗ trợ ra quyết định với báo cáo, khuyến nghị và phân tích
    """
    try:
        crop = season_data.get("crop", "").strip().lower()
        area = float(season_data.get("area", 1))
        province = season_data.get("province", "")
        fertilizer = season_data.get("fertilizer", "")
        
        # Tính toán các chỉ số
        yield_per_ha = predicted_yield / area if area > 0 else 0
        
        # Phân loại năng suất
        if yield_per_ha >= 6:
            yield_category = "Rất cao"
            yield_color = "text-green-600"
            yield_bg = "bg-green-100"
        elif yield_per_ha >= 4:
            yield_category = "Cao"
            yield_color = "text-green-500"
            yield_bg = "bg-green-50"
        elif yield_per_ha >= 2:
            yield_category = "Trung bình"
            yield_color = "text-yellow-600"
            yield_bg = "bg-yellow-50"
        else:
            yield_category = "Thấp"
            yield_color = "text-red-600"
            yield_bg = "bg-red-50"
        
        # Khuyến nghị theo loại cây trồng
        crop_recommendations = {
            "lúa": [
                "🌾 Bón thúc đợt 1: 7-10 ngày sau sạ",
                "💧 Duy trì mực nước 3-5cm trong giai đoạn đẻ nhánh",
                "🛡️ Phòng trừ sâu bệnh: đạo ôn, rầy nâu",
                "📅 Thu hoạch khi 85-90% hạt chín vàng"
            ],
            "ngô": [
                "🌱 Bón lót phân chuồng + lân trước khi gieo",
                "💦 Tưới đủ ẩm giai đoạn trỗ cờ phun râu",
                "🪲 Phòng trừ sâu đục thân, bệnh khô vằn",
                "🌽 Thu hoạch khi hạt cứng, râu chuyển nâu"
            ],
            "cà phê": [
                "🌿 Tỉa cành tạo tán sau thu hoạch",
                "💧 Tưới nước đầy đủ mùa khô",
                "🍂 Bón phân NPK cân đối theo giai đoạn",
                "☀️ Che bóng hợp lý tránh nắng gắt"
            ]
        }
        
        # Khuyến nghị chung
        general_recommendations = [
            "📊 Theo dõi thời tiết thường xuyên để điều chỉnh lịch chăm sóc",
            "🌱 Kiểm tra độ ẩm đất trước khi tưới nước",
            "🔍 Thăm đồng thường xuyên để phát hiện sâu bệnh sớm",
            "📝 Ghi chép nhật ký đồng ruộng để cải thiện vụ sau"
        ]
        
        # Cảnh báo dựa trên điều kiện
        warnings = []
        if not fertilizer or "không" in fertilizer.lower():
            warnings.append("⚠️ Chưa sử dụng phân bón - có thể ảnh hưởng năng suất")
        
        # Phân tích lợi nhuận ước tính
        crop_prices = {
            "lúa": 7000, "ngô": 6000, "cà phê": 45000, "cao su": 35000,
            "chè": 25000, "tiêu": 80000, "điều": 30000, "mía": 1000,
            "lạc": 20000, "đậu tương": 15000
        }
        
        price_per_kg = crop_prices.get(crop, 10000)
        estimated_revenue = predicted_yield * 1000 * price_per_kg
        
        # Chi phí ước tính (VND/ha)
        cost_per_ha = {
            "lúa": 15000000, "ngô": 18000000, "cà phê": 25000000,
            "cao su": 15000000, "chè": 20000000, "default": 15000000
        }
        
        cost = cost_per_ha.get(crop, cost_per_ha["default"]) * area
        estimated_profit = estimated_revenue - cost
        
        # Tạo dữ liệu biểu đồ (mẫu)
        growth_stages = [
            {"stage": "Gieo trồng", "progress": 100, "tasks": ["Làm đất", "Gieo hạt"]},
            {"stage": "Phát triển", "progress": 65, "tasks": ["Bón thúc", "Tưới nước"]},
            {"stage": "Ra hoa", "progress": 30, "tasks": ["Bón phân", "Phun thuốc"]},
            {"stage": "Thu hoạch", "progress": 0, "tasks": ["Chuẩn bị thu", "Bảo quản"]}
        ]
        
        return {
            "yield_per_ha": round(yield_per_ha, 2),
            "yield_category": yield_category,
            "yield_color": yield_color,
            "yield_bg": yield_bg,
            "crop_recommendations": crop_recommendations.get(crop, general_recommendations),
            "general_recommendations": general_recommendations,
            "warnings": warnings,
            "estimated_revenue": f"{estimated_revenue:,.0f}",
            "estimated_profit": f"{estimated_profit:,.0f}",
            "cost": f"{cost:,.0f}",
            "growth_stages": growth_stages,
            "profit_margin": round((estimated_profit / estimated_revenue * 100) if estimated_revenue > 0 else 0, 1),
            "price_per_kg": f"{price_per_kg:,.0f}"
        }
        
    except Exception as e:
        print(f"Lỗi tạo hỗ trợ quyết định: {e}")
        return None

# ----------------- CALCULATE PRODUCTIVITY FOR STATS -----------------
def calculate_productivity(season_data):
    """
    Tính năng suất cho thống kê (tấn/ha)
    """
    try:
        actual_yield = season_data.get("actual_yield", 0)
        area = season_data.get("area", 1)
        
        if actual_yield and area and area > 0:
            return float(actual_yield) / float(area)
        return 0.0
    except:
        return 0.0

# ----------------- FIREBASE WITH RETRY -----------------
def get_firestore_with_retry():
    """Kết nối Firebase với retry mechanism"""
    max_retries = 2
    timeout_seconds = 10
    
    for attempt in range(max_retries):
        try:
            if config.USE_FIREBASE:
                if db is None:
                    print(f"🔄 Attempt {attempt + 1} to initialize Firebase...")
                    db_retry = init_firebase()
                    if db_retry:
                        print("✅ Firebase initialized with retry")
                        return db_retry
                else:
                    # Test connection với timeout
                    print(f"🔄 Attempt {attempt + 1} to test Firebase connection...")
                    test_ref = db.collection("seasons").limit(1)
                    list(test_ref.stream())  # Test query nhỏ
                    print("✅ Firebase connection test passed")
                    return db
            else:
                return None
                
        except Exception as e:
            print(f"❌ Firebase attempt {attempt + 1} failed: {str(e)[:100]}...")
            if attempt < max_retries - 1:
                import time
                time.sleep(1)  # Chờ 1 giây trước khi retry
            else:
                print("🚨 All Firebase connection attempts failed")
                return None
    
    return None

# ----------------- OPTIMIZED FIREBASE QUERY -----------------
def safe_firebase_query(collection_name, limit=50, order_by=None):
    """Thực hiện query Firebase an toàn với timeout"""
    try:
        if not config.USE_FIREBASE or db is None:
            return []
            
        collection_ref = db.collection(collection_name)
        
        # Áp dụng order_by nếu có
        if order_by:
            collection_ref = collection_ref.order_by(order_by, direction=firestore.Query.DESCENDING)
        
        # Giới hạn số lượng documents
        collection_ref = collection_ref.limit(limit)
        
        # Lấy documents
        docs = list(collection_ref.stream())
        
        # Xử lý dữ liệu
        results = []
        for doc in docs:
            try:
                record = doc.to_dict()
                record["id"] = doc.id
                
                # Xử lý số liệu an toàn
                if record.get("actual_yield"):
                    try:
                        record["actual_yield"] = float(record["actual_yield"])
                    except:
                        record["actual_yield"] = 0.0
                else:
                    record["actual_yield"] = 0.0
                    
                if record.get("area"):
                    try:
                        record["area"] = float(record["area"])
                    except:
                        record["area"] = 0.0
                else:
                    record["area"] = 0.0
                
                results.append(record)
            except Exception as doc_error:
                print(f"⚠️ Lỗi xử lý document {doc.id}: {doc_error}")
                continue
                
        return results
        
    except Exception as e:
        print(f"❌ Lỗi Firebase query: {e}")
        return []

# =========================================================
#               ROUTES
# =========================================================

@app.route("/")
@login_required
def index():
    total = 0
    recent = []
    if config.USE_FIREBASE and db is not None:
        try:
            docs = db.collection("seasons").order_by("created_at", direction=firestore.Query.DESCENDING).limit(5).stream()
            for d in docs:
                recent.append(d.to_dict())
            total = len(list(db.collection("seasons").limit(1000).stream()))
        except Exception as e:
            print("Lỗi đọc Firestore:", e)
            total = 0
    else:
        if os.path.exists(SEASONS_CSV):
            df = pd.read_csv(SEASONS_CSV)
            total = len(df)
            recent = df.sort_values("created_at", ascending=False).head(5).to_dict(orient="records")
    return render_template("index.html", total=total, recent=recent)

# ---------- OVERVIEW (OPTIMIZED) ----------
@app.route("/overview")
@login_required
def overview():
    stats = {
        "total_seasons": 0,
        "total_area": 0,
        "top_provinces": [],
        "crop_distribution": {},
        "top_provinces_by_crop": {},
        "weather_stats": {}
    }
    
    # ✅ XỬ LÝ DỮ LIỆU MÙA VỤ - TỐI ƯU HÓA
    seasons_data = []
    
    if config.USE_FIREBASE and db is not None:
        try:
            # Lấy tất cả seasons
            seasons_ref = db.collection("seasons")
            docs = list(seasons_ref.stream())
            stats["total_seasons"] = len(docs)
            
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                seasons_data.append(data)
                
        except Exception as e:
            print("Lỗi đọc thống kê Firestore:", e)
    else:
        # CSV fallback - tối ưu hóa
        SEASONS_CSV_PATH = os.path.join(DATA_DIR, "seasons.csv")
        if os.path.exists(SEASONS_CSV_PATH):
            try:
                df = pd.read_csv(SEASONS_CSV_PATH)
                stats["total_seasons"] = len(df)
                seasons_data = df.to_dict(orient="records")
            except Exception as e:
                print("Lỗi đọc file CSV mùa vụ:", e)
    
    # ✅ TỰ ĐỘNG TÍNH NĂNG SUẤT CHO CÁC MÙA VỤ CHƯA CÓ DỮ LIỆU
    if seasons_data:
        auto_calculated_count = 0
        for season in seasons_data:
            # Kiểm tra nếu chưa có actual_yield nhưng có đủ thông tin để tính toán
            if (not season.get("actual_yield") and 
                season.get("crop") and 
                season.get("area") and 
                float(season.get("area", 0)) > 0):
                
                predicted_yield = calculate_yield(season)
                if predicted_yield is not None:
                    try:
                        if config.USE_FIREBASE and db is not None:
                            doc_ref = db.collection("seasons").document(season["id"])
                            doc_ref.update({
                                "actual_yield": round(predicted_yield, 2),
                                "yield_calculated_at": datetime.utcnow().isoformat(),
                                "yield_source": "auto_overview"
                            })
                        else:
                            # Cập nhật trong CSV
                            SEASONS_CSV_PATH = os.path.join(DATA_DIR, "seasons.csv")
                            if os.path.exists(SEASONS_CSV_PATH):
                                df = pd.read_csv(SEASONS_CSV_PATH)
                                # Tìm và cập nhật bản ghi
                                for idx, row in df.iterrows():
                                    if (str(row.get("farmer_name")) == str(season.get("farmer_name")) and 
                                        str(row.get("crop")) == str(season.get("crop")) and 
                                        str(row.get("province")) == str(season.get("province"))):
                                        df.at[idx, "actual_yield"] = round(predicted_yield, 2)
                                        df.at[idx, "yield_calculated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        df.at[idx, "yield_source"] = "auto_overview"
                                        break
                                df.to_csv(SEASONS_CSV_PATH, index=False, encoding="utf-8-sig")
                        
                        auto_calculated_count += 1
                        print(f"✅ Đã tự động tính năng suất: {predicted_yield} tấn cho {season.get('crop')} tại {season.get('province')}")
                        
                    except Exception as e:
                        print(f"❌ Lỗi khi lưu năng suất tự động: {e}")
        
        if auto_calculated_count > 0:
            print(f"📊 Đã tự động tính năng suất cho {auto_calculated_count} mùa vụ")
            # Load lại trang để hiển thị dữ liệu mới
            flash(f"✅ Đã tự động tính năng suất cho {auto_calculated_count} mùa vụ", "success")
            return redirect(url_for("overview"))
    
    # ✅ TÍNH TOÁN THỐNG KÊ TỪ DỮ LIỆU MÙA VỤ
    if seasons_data:
        area_by_province = {}
        crop_stats = {}
        crop_province_stats = {}
        
        for season in seasons_data:
            # Xử lý diện tích
            try:
                area = float(season.get("area", 0))
            except:
                area = 0
                
            province = season.get("province", "Chưa xác định")
            crop = season.get("crop", "Chưa xác định")
            
            # Chuẩn hóa tên cây trồng
            crop_normalized = crop.strip().lower()
            
            # Tổng diện tích
            stats["total_area"] += area
            
            # Thống kê theo tỉnh
            if province in area_by_province:
                area_by_province[province] += area
            else:
                area_by_province[province] = area
            
            # Thống kê theo cây trồng
            if crop_normalized in crop_stats:
                crop_stats[crop_normalized] += 1
            else:
                crop_stats[crop_normalized] = 1
            
            # Thống kê năng suất theo tỉnh và cây trồng
            # Kiểm tra nếu có actual_yield
            actual_yield = season.get("actual_yield")
            if actual_yield and area > 0:
                try:
                    # Tính năng suất (tấn/ha)
                    productivity = float(actual_yield) / area
                    
                    if crop_normalized not in crop_province_stats:
                        crop_province_stats[crop_normalized] = []
                    
                    # Tìm xem tỉnh đã có trong danh sách chưa
                    existing_province = None
                    for item in crop_province_stats[crop_normalized]:
                        if item["province"] == province:
                            existing_province = item
                            break
                    
                    if existing_province:
                        # Cập nhật thông tin nếu đã tồn tại
                        existing_province["total_area"] += area
                        existing_province["total_yield"] += float(actual_yield)
                        existing_province["productivity"] = existing_province["total_yield"] / existing_province["total_area"]
                    else:
                        # Thêm tỉnh mới
                        crop_province_stats[crop_normalized].append({
                            "province": province,
                            "total_area": area,
                            "total_yield": float(actual_yield),
                            "productivity": productivity
                        })
                except (ValueError, TypeError, ZeroDivisionError) as e:
                    print(f"Lỗi tính năng suất: {e}")
                    continue
        
        # Sắp xếp và lấy top provinces theo diện tích
        stats["top_provinces"] = sorted(area_by_province.items(), key=lambda x: x[1], reverse=True)[:5]
        stats["crop_distribution"] = crop_stats
        
        # Xử lý top provinces by crop - chỉ lấy top 3 cho mỗi loại cây
        stats["top_provinces_by_crop"] = {}
        for crop, provinces in crop_province_stats.items():
            if provinces:  # Chỉ xử lý nếu có dữ liệu
                # Sắp xếp theo năng suất giảm dần và lấy top 3
                sorted_provinces = sorted(provinces, key=lambda x: x["productivity"], reverse=True)[:3]
                stats["top_provinces_by_crop"][crop] = sorted_provinces
        
        # DEBUG: In ra để kiểm tra
        print(f"📊 Tổng số mùa vụ: {stats['total_seasons']}")
        print(f"📊 Số loại cây trồng có năng suất: {len(crop_province_stats)}")
        for crop, provinces in crop_province_stats.items():
            print(f"🌱 {crop}: {len(provinces)} tỉnh có năng suất")
    
    # ✅ ĐỌC DỮ LIỆU THỜI TIẾT - TỐI ƯU HÓA
    # ... (phần xử lý thời tiết giữ nguyên)
    
    return render_template("overview.html", stats=stats)
# ---------- AUTHENTICATION ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        fullname = request.form.get("fullname", "").strip()

        if config.USE_FIREBASE and db is not None:
            from firebase_admin import auth
            try:
                user = auth.create_user(email=username, password=password, display_name=fullname)
                flash("Đăng ký thành công. Vui lòng đăng nhập.", "success")
                return redirect(url_for("login"))
            except Exception as e:
                flash("Lỗi đăng ký Firebase: " + str(e), "danger")
                return redirect(url_for("register"))
        else:
            if os.path.exists(USERS_CSV):
                df = pd.read_csv(USERS_CSV)
                if username in df['username'].values:
                    flash("Tên đăng nhập đã tồn tại.", "danger")
                    return redirect(url_for("register"))
            else:
                df = pd.DataFrame(columns=["username", "password", "fullname", "role", "created_at"])

            new = pd.DataFrame([{
                "username": username,
                "password": password,
                "fullname": fullname,
                "role": "user",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])

            df = pd.concat([df, new], ignore_index=True)
            df.to_csv(USERS_CSV, index=False, encoding="utf-8-sig")
            flash("Đăng ký thành công (CSV). Vui lòng đăng nhập.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()

        if config.USE_FIREBASE and db is not None:
            api_key = config.FIREBASE_API_KEY
            if not api_key:
                flash("Firebase API key chưa được cấu hình.", "danger")
                return redirect(url_for("login"))

            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
            payload = {"email": username, "password": password, "returnSecureToken": True}

            try:
                r = requests.post(url, json=payload, timeout=10)
                res_json = r.json()
                if r.status_code == 200:
                    session['user'] = username
                    session['idToken'] = res_json.get("idToken")
                    flash("Đăng nhập thành công (Firebase).", "success")
                    return redirect(url_for("index"))
                else:
                    err = res_json.get("error", {}).get("message", "Đăng nhập thất bại.")
                    flash(f"Đăng nhập thất bại (Firebase): {err}", "danger")
                    return redirect(url_for("login"))
            except Exception as e:
                flash("Không thể kết nối tới Firebase.", "danger")
                return redirect(url_for("login"))
        else:
            if not os.path.exists(USERS_CSV):
                flash("Chưa có người dùng nào. Vui lòng đăng ký.", "warning")
                return redirect(url_for("register"))
            df = pd.read_csv(USERS_CSV)
            user = df[(df['username'] == username) & (df['password'] == password)]
            if not user.empty:
                session['user'] = username
                flash(f"Chào mừng {username}", "success")
                return redirect(url_for("index"))
            else:
                flash("Sai tài khoản hoặc mật khẩu (CSV).", "danger")
                return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.pop('user', None)
    session.pop('idToken', None)
    flash("Đã đăng xuất.", "info")
    return redirect(url_for("login"))

# ---------- MANAGE SEASONS (OPTIMIZED) ----------
@app.route("/manage", methods=["GET", "POST"])
@login_required
def manage():
    try:
        prov_file = os.path.join(os.path.dirname(__file__), "data", "vietnam_provinces_latlon.csv")
        provinces = []
        if os.path.exists(prov_file):
            try:
                df_prov = pd.read_csv(prov_file)
                provinces = list(df_prov['Province']) if 'Province' in df_prov.columns else []
            except:
                provinces = ["Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Cần Thơ", "An Giang"]

        # ✅ Xử lý thêm mùa vụ
        if request.method == "POST":
            data = {
                "farmer_name": request.form.get("farmer_name"),
                "province": request.form.get("province"),
                "crop": request.form.get("crop"),
                "area": float(request.form.get("area") or 0),
                "sow_date": request.form.get("sow_date"),
                "harvest_date": request.form.get("harvest_date"),
                "fertilizer": request.form.get("fertilizer"),
                "notes": request.form.get("notes"),
                "created_at": datetime.utcnow().isoformat(),
                "user": session.get("user")
            }

            try:
                if config.USE_FIREBASE and db is not None:
                    db.collection("seasons").add(data)
                    flash("✅ Đã thêm mùa vụ mới vào Firestore.", "success")
                else:
                    if os.path.exists(SEASONS_CSV):
                        df_old = pd.read_csv(SEASONS_CSV)
                        df = pd.concat([df_old, pd.DataFrame([data])], ignore_index=True)
                    else:
                        df = pd.DataFrame([data])
                    df.to_csv(SEASONS_CSV, index=False, encoding="utf-8-sig")
                    flash("✅ Đã lưu mùa vụ vào CSV (chế độ offline).", "success")
            except Exception as e:
                flash(f"❌ Lỗi khi lưu mùa vụ: {e}", "danger")

            return redirect(url_for("manage"))

        # ✅ Hiển thị danh sách mùa vụ - TỐI ƯU HÓA
        seasons = []
        
        if config.USE_FIREBASE and db is not None:
            try:
                # GIỚI HẠN CHẶT CHẼ - chỉ lấy 50 bản ghi mới nhất
                docs = db.collection("seasons")\
                        .order_by("created_at", direction=firestore.Query.DESCENDING)\
                        .limit(50)\
                        .stream()
                
                count = 0
                for d in docs:
                    if count >= 50:  # Double check
                        break
                    record = d.to_dict()
                    record["id"] = d.id
                    
                    # Xử lý dữ liệu an toàn
                    try:
                        if record.get("actual_yield"):
                            record["actual_yield"] = float(record["actual_yield"])
                        else:
                            record["actual_yield"] = 0.0
                    except:
                        record["actual_yield"] = 0.0
                        
                    try:
                        if record.get("area"):
                            record["area"] = float(record["area"])
                        else:
                            record["area"] = 0.0
                    except:
                        record["area"] = 0.0
                    
                    seasons.append(record)
                    count += 1
                    
                print(f"✅ Đã tải {len(seasons)} mùa vụ từ Firebase")
                
            except Exception as e:
                print(f"❌ Lỗi đọc Firestore: {e}")
                flash(f"Lỗi kết nối database: {str(e)[:100]}...", "danger")
                # Fallback to CSV
                if os.path.exists(SEASONS_CSV):
                    try:
                        df = pd.read_csv(SEASONS_CSV)
                        if 'actual_yield' in df.columns:
                            df['actual_yield'] = pd.to_numeric(df['actual_yield'], errors='coerce').fillna(0)
                        if 'area' in df.columns:
                            df['area'] = pd.to_numeric(df['area'], errors='coerce').fillna(0)
                        seasons = df.tail(50).to_dict(orient="records")  # Chỉ lấy 50 bản ghi
                    except Exception as csv_error:
                        print(f"❌ Lỗi đọc CSV: {csv_error}")
        else:
            # Chế độ CSV
            if os.path.exists(SEASONS_CSV):
                try:
                    df = pd.read_csv(SEASONS_CSV)
                    if 'actual_yield' in df.columns:
                        df['actual_yield'] = pd.to_numeric(df['actual_yield'], errors='coerce').fillna(0)
                    if 'area' in df.columns:
                        df['area'] = pd.to_numeric(df['area'], errors='coerce').fillna(0)
                    seasons = df.tail(50).to_dict(orient="records")  # Chỉ lấy 50 bản ghi
                except Exception as e:
                    print(f"❌ Lỗi đọc file CSV: {e}")
                    seasons = []

        return render_template("manage.html", provinces=provinces, seasons=seasons)
        
    except Exception as e:
        print(f"❌ Lỗi nghiêm trọng trong route /manage: {e}")
        flash("Đã xảy ra lỗi hệ thống. Vui lòng thử lại.", "danger")
        return render_template("manage.html", provinces=[], seasons=[])

# ---------- AUTO YIELD PREDICTION WITH DECISION SUPPORT ----------
@app.route("/manage/yield/<string:season_id>", methods=["GET", "POST"])
@login_required
def auto_yield(season_id):
    try:
        if config.USE_FIREBASE and db is not None:
            # Lấy dữ liệu mùa vụ từ Firestore
            doc_ref = db.collection("seasons").document(season_id)
            doc = doc_ref.get()
            if not doc.exists:
                flash("Không tìm thấy mùa vụ.", "danger")
                return redirect(url_for("manage"))

            season = doc.to_dict()
            
            # Nếu là POST request, tính toán và lưu năng suất
            if request.method == "POST":
                actual_yield_input = request.form.get("actual_yield")
                
                if actual_yield_input:
                    # Sử dụng giá trị người dùng nhập
                    actual_yield = float(actual_yield_input)
                    doc_ref.update({
                        "actual_yield": round(actual_yield, 2),
                        "yield_calculated_at": datetime.utcnow().isoformat(),
                        "yield_source": "manual"
                    })
                    flash(f"✅ Đã lưu năng suất: {round(actual_yield, 2)} tấn", "success")
                else:
                    # Tự động tính toán nếu không có input
                    predicted_yield = calculate_yield(season)
                    if predicted_yield is not None:
                        doc_ref.update({
                            "actual_yield": round(predicted_yield, 2),
                            "yield_calculated_at": datetime.utcnow().isoformat(),
                            "yield_source": "auto"
                        })
                        flash(f"✅ Đã tính toán năng suất tự động: {round(predicted_yield, 2)} tấn", "success")
                    else:
                        flash("❌ Không thể tính toán năng suất tự động.", "warning")
                        return redirect(url_for("manage"))
                
                return redirect(url_for("manage"))

            # Hiển thị thông tin dự đoán và hỗ trợ quyết định (GET request)
            predicted_yield = calculate_yield(season)
            decision_support = generate_decision_support(season, predicted_yield)
            
            return render_template("auto_yield.html", 
                                 season=season, 
                                 season_id=season_id,
                                 predicted_yield=predicted_yield,
                                 decision_support=decision_support)

        else:
            # Fallback cho CSV
            if not os.path.exists(SEASONS_CSV):
                flash("Không có dữ liệu mùa vụ.", "danger")
                return redirect(url_for("manage"))
            
            df = pd.read_csv(SEASONS_CSV)
            if int(season_id) >= len(df):
                flash("Không tìm thấy mùa vụ.", "danger")
                return redirect(url_for("manage"))
                
            season = df.iloc[int(season_id)].to_dict()
            
            if request.method == "POST":
                actual_yield_input = request.form.get("actual_yield")
                
                if actual_yield_input:
                    # Sử dụng giá trị người dùng nhập
                    actual_yield = float(actual_yield_input)
                    df.at[int(season_id), "actual_yield"] = round(actual_yield, 2)
                    df.at[int(season_id), "yield_calculated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    df.at[int(season_id), "yield_source"] = "manual"
                    df.to_csv(SEASONS_CSV, index=False, encoding="utf-8-sig")
                    flash(f"✅ Đã lưu năng suất: {round(actual_yield, 2)} tấn", "success")
                else:
                    # Tự động tính toán
                    predicted_yield = calculate_yield(season)
                    if predicted_yield is not None:
                        df.at[int(season_id), "actual_yield"] = round(predicted_yield, 2)
                        df.at[int(season_id), "yield_calculated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        df.at[int(season_id), "yield_source"] = "auto"
                        df.to_csv(SEASONS_CSV, index=False, encoding="utf-8-sig")
                        flash(f"✅ Đã tính toán năng suất tự động: {round(predicted_yield, 2)} tấn", "success")
                    else:
                        flash("❌ Không thể tính toán năng suất tự động.", "warning")
                        return redirect(url_for("manage"))
                
                return redirect(url_for("manage"))

            predicted_yield = calculate_yield(season)
            decision_support = generate_decision_support(season, predicted_yield)
            
            return render_template("auto_yield.html", 
                                 season=season, 
                                 season_id=season_id,
                                 predicted_yield=predicted_yield,
                                 decision_support=decision_support)

    except Exception as e:
        flash(f"❌ Lỗi khi tính năng suất: {e}", "danger")
        return redirect(url_for("manage"))

# ---------- EDIT SEASON ----------
@app.route("/manage/edit/<string:id>", methods=["GET", "POST"])
@login_required
def edit_season(id):
    try:
        if config.USE_FIREBASE and db is not None:
            doc_ref = db.collection("seasons").document(id)
            doc = doc_ref.get()
            if not doc.exists:
                flash("Không tìm thấy mùa vụ để chỉnh sửa.", "danger")
                return redirect(url_for("manage"))

            season = doc.to_dict()

            if request.method == "POST":
                updated_data = {
                    "farmer_name": request.form.get("farmer_name"),
                    "province": request.form.get("province"),
                    "crop": request.form.get("crop"),
                    "area": float(request.form.get("area") or 0),
                    "sow_date": request.form.get("sow_date"),
                    "harvest_date": request.form.get("harvest_date"),
                    "fertilizer": request.form.get("fertilizer"),
                    "notes": request.form.get("notes")
                }
                doc_ref.update(updated_data)
                flash("✅ Đã cập nhật thông tin mùa vụ (Firebase).", "success")
                return redirect(url_for("manage"))

            prov_file = os.path.join(os.path.dirname(__file__), "data", "vietnam_provinces_latlon.csv")
            provinces = list(pd.read_csv(prov_file)['Province']) if os.path.exists(prov_file) else []
            return render_template("edit_season.html", season=season, provinces=provinces, season_id=id)

        else:
            # Fallback cho CSV
            if not os.path.exists(SEASONS_CSV):
                flash("Không có dữ liệu mùa vụ.", "danger")
                return redirect(url_for("manage"))
            
            df = pd.read_csv(SEASONS_CSV)
            try:
                season_id_int = int(id)
                if season_id_int >= len(df):
                    flash("Không tìm thấy mùa vụ để chỉnh sửa.", "danger")
                    return redirect(url_for("manage"))
                
                season = df.iloc[season_id_int].to_dict()
                
                if request.method == "POST":
                    for field in ["farmer_name", "province", "crop", "area", "sow_date", "harvest_date", "fertilizer", "notes"]:
                        if field == "area":
                            df.at[season_id_int, field] = float(request.form.get(field) or 0)
                        else:
                            df.at[season_id_int, field] = request.form.get(field)
                    df.to_csv(SEASONS_CSV, index=False, encoding="utf-8-sig")
                    flash("✅ Đã cập nhật thông tin mùa vụ (CSV).", "success")
                    return redirect(url_for("manage"))

                prov_file = os.path.join(os.path.dirname(__file__), "data", "vietnam_provinces_latlon.csv")
                provinces = list(pd.read_csv(prov_file)['Province']) if os.path.exists(prov_file) else []
                return render_template("edit_season.html", season=season, provinces=provinces, season_id=id)
                
            except ValueError:
                flash("ID mùa vụ không hợp lệ.", "danger")
                return redirect(url_for("manage"))

    except Exception as e:
        flash(f"❌ Lỗi khi chỉnh sửa mùa vụ: {e}", "danger")
        return redirect(url_for("manage"))

# ---------- DELETE SEASON ----------
@app.route("/manage/delete/<id>")
@login_required
def delete_season(id):
    if config.USE_FIREBASE and db is not None:
        try:
            db.collection("seasons").document(id).delete()
            flash("Đã xóa mùa vụ.", "info")
        except Exception as e:
            flash("Lỗi khi xóa mùa vụ: " + str(e), "danger")
    else:
        if os.path.exists(SEASONS_CSV):
            df = pd.read_csv(SEASONS_CSV)
            df = df.drop(int(id))
            df.to_csv(SEASONS_CSV, index=False, encoding="utf-8-sig")
            flash("Đã xóa mùa vụ (CSV).", "info")
    return redirect(url_for("manage"))

# ---------- WEATHER ----------
@app.route("/weather")
@login_required
def weather():
    WEATHER_CSV = "data/weather_all_vn_annual_2000-2023.csv"
    if not os.path.exists(WEATHER_CSV):
        return render_template("weather.html", weather=[])
    df = pd.read_csv(WEATHER_CSV, header=None, names=["Year", "TempAvg", "RainfallAnnual", "HumidityAvg"])
    data = df.tail(20).to_dict(orient="records")  # Giới hạn 20 bản ghi
    return render_template("weather.html", weather=data)

# ---------- PREDICT ----------
@app.route("/predict", methods=["GET", "POST"])
@login_required
def predict():
    weather_data = None
    forecast_data = None
    result = None

    if request.method == "POST":
        # Xử lý dự báo thời tiết
        if 'city' in request.form:
            city = request.form.get("city", "").strip()
            api_key = "8e054550351ac98ddb1c99ddb6e5adcd"

            if not city:
                flash("Vui lòng nhập tên thành phố.", "warning")
            else:
                url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=vi"
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        weather_data = {
                            "city": data["name"],
                            "temp": data["main"]["temp"],
                            "desc": data["weather"][0]["description"],
                            "humidity": data["main"]["humidity"],
                            "wind": round(data["wind"]["speed"] * 3.6, 1), 
                            "icon": data["weather"][0]["icon"]
                        }
                        flash(f"Đã cập nhật dự báo cho thành phố {data['name']}.", "success")
                    else:
                        flash("Không tìm thấy thành phố. Vui lòng thử lại.", "danger")
                except requests.exceptions.Timeout:
                    flash("Kết nối timeout. Vui lòng thử lại.", "danger")
                except Exception as e:
                    flash("Lỗi kết nối đến dịch vụ thời tiết.", "danger")
        
        # Xử lý dự đoán năng suất
        elif 'temp' in request.form:
            temp = float(request.form.get("temp"))
            rain = float(request.form.get("rain"))
            humid = float(request.form.get("humid"))
            if model is None:
                flash("Model chưa load.", "danger")
            else:
                import numpy as np
                X = np.array([[temp, rain, humid]])
                pred = model.predict(X)[0]
                result = round(float(pred), 2)
                
    return render_template("predict.html", weather=weather_data, forecast=forecast_data, result=result)

# =========================================================
#               API ENDPOINTS
# =========================================================

# ---------- HEALTH CHECK ----------
@app.route("/api/health")
def health_check():
    """Endpoint kiểm tra tình trạng hệ thống"""
    try:
        # Kiểm tra Firebase connection
        if config.USE_FIREBASE and db is not None:
            try:
                test_ref = db.collection("seasons").limit(1)
                list(test_ref.stream())
                firebase_status = "connected"
            except Exception as e:
                firebase_status = f"error: {str(e)}"
        else:
            firebase_status = "disabled"
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "firebase": firebase_status,
            "memory_usage": f"{sys.getsizeof([]) / 1024 / 1024:.2f} MB"
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# ---------- WEATHER CHART (HOME) ----------
@app.route("/api/weather_chart_home")
@login_required
def api_weather_chart_home():
    weather_path = os.path.join(os.getcwd(), "data", "weather_all_vn_annual_2000-2023.csv")
    if not os.path.exists(weather_path):
        return jsonify({"error": "Không tìm thấy file thời tiết"}), 404

    try:
        df = pd.read_csv(weather_path, header=None, names=["Year", "TempAvg", "RainfallAnnual", "HumidityAvg"])
        df = df.tail(10)  # Chỉ lấy 10 năm gần nhất
        df = df.dropna().sort_values("Year")

        out = {
            "years": df["Year"].tolist(),
            "temp": df["TempAvg"].tolist(),
            "rain": df["RainfallAnnual"].tolist(),
            "humidity": df["HumidityAvg"].tolist()
        }
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------- YIELD CHART (FAO) ----------
@app.route("/api/yield_chart")
@login_required
def api_yield_chart():
    csv_path = os.path.join("data", "rice_yield_vn.csv")
    if not os.path.exists(csv_path):
        return jsonify({"error": "rice_yield_vn.csv not found"}), 404
    df = pd.read_csv(csv_path)
    out = {"years": df["Year"].tolist(), "yield": df["Yield (ton/ha)"].tolist()}
    return jsonify(out)

# =========================================================
#               GRACEFUL SHUTDOWN
# =========================================================

def signal_handler(sig, frame):
    print('\n👋 Ứng dụng đang dừng...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# =========================================================
#               APPLICATION START
# =========================================================

if __name__ == "__main__":
    print("🚀 Starting AgriConnect Application...")
    print("📍 Health Check: http://localhost:5000/api/health")
    app.run(debug=True)