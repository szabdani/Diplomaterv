import pandas as pd
from kloppy import wyscout

file_path = r"D:\Dani\BME\felev_11\Dipterv1\repo\wyscout-soccer-match-event-dataset\processed-v2\files\1694390.json"
dataset = wyscout.load(event_data=file_path)

df = dataset.to_df()

# Basic Event EDA
print("Events (rows, columns):", df.shape)

print("\nColumn names:")
print(df.columns.tolist())

print("\nEvent counts:")
print(df['event_type'].value_counts())

print("\nShot rows:")
print(df[df['event_type'] == 'SHOT'])