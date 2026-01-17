import pandas as pd

# Đường dẫn đến file CSV bạn đã tải
input_file = '../data/FAOSTAT_data.csv'
output_file = '../data/rice_yield_vn.csv'

# Đọc file CSV
df = pd.read_csv(input_file)

# Kiểm tra xem các cột có đúng như mong đợi không
print("Các cột trong file:", df.columns.tolist())

# Lọc dữ liệu cho Việt Nam - Rice - Yield
df = df[(df['Area'].str.contains('Viet', case=False)) &
        (df['Item'].str.contains('Rice', case=False)) &
        (df['Element'].str.contains('Yield', case=False))]

# Chuyển kiểu dữ liệu
df['Year'] = pd.to_numeric(df['Year'], errors='coerce')
df['Value'] = pd.to_numeric(df['Value'], errors='coerce')

# Dữ liệu của bạn hiện là kg/ha → đổi sang tấn/ha
df['Yield (ton/ha)'] = df['Value'] / 1000

# Giữ lại 2 cột cần thiết
clean_df = df[['Year', 'Yield (ton/ha)']].dropna().sort_values('Year')

# Xuất dữ liệu sạch
clean_df.to_csv(output_file, index=False)

print(f'✅ Đã lưu file sạch tại: {output_file}')
print(clean_df.head(10))
