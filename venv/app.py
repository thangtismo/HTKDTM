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