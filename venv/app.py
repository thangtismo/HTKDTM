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