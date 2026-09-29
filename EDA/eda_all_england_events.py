import pandas as pd

file_path = r"D:\Dani\BME\felev_11\Dipterv1\repo\wyscout-soccer-match-event-dataset\events_England.json"

df = pd.read_json(file_path)

# Basic Event EDA
print("Events (rows, columns):", df.shape)
print("All data:")
print(df)
print("\nColumn names:")
print(df.columns.tolist())
print("\nEvent counts:")
print(df['eventName'].value_counts())