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
                    flash("Lỗi kết nối đến dịch vụ thời tiết.", "danger"