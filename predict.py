import os
import json
import sys
import joblib
import pandas as pd
import numpy as np
from models import PureNumPyPipeline

# Bind PureNumPyPipeline to __main__ so joblib unpickles cleanly across entrypoints
sys.modules['__main__'].PureNumPyPipeline = PureNumPyPipeline

CURRENT_YEAR = 2025

class HousePricePredictor:
    def __init__(self, model_path='best_house_price_model.joblib', meta_path='model_metadata.json'):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = os.path.join(script_dir, model_path)
        self.meta_path = os.path.join(script_dir, meta_path)
        
        if not os.path.exists(self.model_path) or not os.path.exists(self.meta_path):
            raise FileNotFoundError(
                "Model files not found! Please run `python train_model.py` first."
            )
            
        self.pipeline = joblib.load(self.model_path)
        with open(self.meta_path, 'r') as f:
            self.metadata = json.load(f)
            
        self.best_model_name = self.metadata['best_model']
        self.rmse = self.metadata['metrics'][self.best_model_name]['rmse']
        self.mae = self.metadata['metrics'][self.best_model_name]['mae']
        self.r2 = self.metadata['metrics'][self.best_model_name]['r2_score']

    def preprocess_input(self, raw_input):
        """Converts raw user dict into DataFrame with feature engineering."""
        df = pd.DataFrame([raw_input])
        
        # Ensure default values for optional fields
        defaults = {
            'sqft': 2000,
            'bedrooms': 3,
            'bathrooms': 2.0,
            'location_tier': 'Suburban',
            'year_built': 2010,
            'garage_cars': 2,
            'school_rating': 7.0,
            'distance_to_city_center_km': 10.0,
            'lot_size_sqft': 5000,
            'renovated': 0
        }
        
        for col, val in defaults.items():
            if col not in df.columns or pd.isna(df[col].iloc[0]):
                df[col] = val
                
        # Engineer features matching train_model.py
        df['house_age'] = CURRENT_YEAR - df['year_built']
        df['total_rooms'] = df['bedrooms'] + df['bathrooms']
        df['sqft_per_room'] = df['sqft'] / (df['total_rooms'] + 0.1)
        df['lot_to_sqft_ratio'] = df['lot_size_sqft'] / (df['sqft'] + 1.0)
        
        return df

    def predict(self, raw_input):
        """
        Runs prediction for raw input features.
        Returns detailed prediction dictionary in Indian Rupees (INR ₹).
        """
        df_input = self.preprocess_input(raw_input)
        
        predicted_price = float(self.pipeline.predict(df_input)[0])
        predicted_price = max(500000.0, round(predicted_price, -4))
        
        # Estimate 90% confidence range (+/- 1.64 * RMSE in INR)
        margin = round(1.64 * self.rmse, -4)
        price_low = max(500000.0, round(predicted_price - margin, -4))
        price_high = round(predicted_price + margin, -4)
        
        price_per_sqft = round(predicted_price / df_input['sqft'].iloc[0], 2)
        
        # Estimated monthly mortgage in India (20-yr @ 8.5% home loan rate, 20% down payment)
        principal = predicted_price * 0.80
        monthly_rate = 0.085 / 12
        num_payments = 240
        monthly_mortgage = round(
            principal * (monthly_rate * (1 + monthly_rate)**num_payments) / 
            ((1 + monthly_rate)**num_payments - 1)
        )
        
        return {
            'predicted_price': predicted_price,
            'confidence_range': {
                'min': price_low,
                'max': price_high
            },
            'price_per_sqft': price_per_sqft,
            'estimated_monthly_mortgage': monthly_mortgage,
            'model_info': {
                'model_name': self.best_model_name,
                'r2_score': self.r2,
                'mae': round(self.mae),
                'rmse': round(self.rmse)
            }
        }

if __name__ == '__main__':
    try:
        predictor = HousePricePredictor()
        sample_house = {
            'sqft': 2400,
            'bedrooms': 4,
            'bathrooms': 2.5,
            'location_tier': 'Urban',
            'year_built': 2018,
            'garage_cars': 2,
            'school_rating': 8.5,
            'distance_to_city_center_km': 6.0,
            'lot_size_sqft': 6000,
            'renovated': 1
        }
        res = predictor.predict(sample_house)
        print("\n--- SAMPLE PREDICTION RESULT ---")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error during prediction test: {e}")
