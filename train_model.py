import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
import joblib
import csv
import os

# Load and prepare the data
try:
    print("Loading data...")
    if not os.path.exists('Dataset.csv'):
        raise FileNotFoundError("Dataset.csv not found. Please ensure the file exists in the current directory.")
    
    data = pd.read_csv('Dataset.csv')

    # Replace 'mΩ' with 'mOhm' in column names
    data.columns = [col.replace('mΩ', 'mOhm') if 'mΩ' in col else col for col in data.columns]

    # Select features for training
    features = ['Capacity (mAh)', 'Voltage (V)', 'Temperature (°C)', 'Internal Resistance (mOhm)']
    target = 'Battery Health (%)'

    # Prepare X and y
    X = data[features]
    y = data[target]

    # Check for missing values
    if X.isnull().values.any() or y.isnull().values.any():
        raise ValueError("Dataset contains missing values")

    # Split the data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train the model
    print("Training model...")
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Evaluate the model
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    print(f"Mean Squared Error: {mse}")

    # Save the model
    try:
        print("Saving model...")
        model_filename = "battery_health_model.pkl"
        joblib.dump(model, model_filename)
        print(f"Model saved as {model_filename}")
    except Exception as e:
        print(f"Failed to save model: {str(e)}")

    # Test prediction
    test_input = pd.DataFrame([[3000, 3.7, 30, 200]], columns=features)
    test_prediction = model.predict(test_input)[0]
    print(f"\nTest prediction for sample input:")
    print(f"Input: Capacity=3000mAh, Voltage=3.7V, Temperature=30°C, Internal Resistance=200mOhm")
    print(f"Predicted Battery Health: {test_prediction:.2f}%")

except Exception as e:
    print(f"An error occurred: {str(e)}")
