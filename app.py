import os
import sys
import json
from flask import Flask, render_template, jsonify, request
from models import PureNumPyPipeline

sys.modules['__main__'].PureNumPyPipeline = PureNumPyPipeline

from predict import HousePricePredictor
from train_model import train_and_evaluate_models

app = Flask(__name__, template_folder='templates', static_folder='static')

# Initialize Predictor (or train if needed)
script_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(script_dir, 'best_house_price_model.joblib')

if not os.path.exists(model_path):
    print("[*] Model not found on server start. Training model...")
    train_and_evaluate_models()

predictor = HousePricePredictor()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/predict', methods=['POST'])
def api_predict():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No input data provided'}), 400
            
        result = predictor.predict(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/metadata', methods=['GET'])
def api_metadata():
    try:
        meta_path = os.path.join(script_dir, 'model_metadata.json')
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        return jsonify(meta)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/presets', methods=['GET'])
def api_presets():
    presets = [
        {
            'id': 'starter',
            'name': '🏡 Starter Cozy Home',
            'data': {
                'sqft': 1150,
                'bedrooms': 2,
                'bathrooms': 1.0,
                'location_tier': 'Budget',
                'year_built': 1995,
                'garage_cars': 1,
                'school_rating': 5.5,
                'distance_to_city_center_km': 18.0,
                'lot_size_sqft': 3500,
                'renovated': 0
            }
        },
        {
            'id': 'suburban',
            'name': '🌳 Family Suburban Villa',
            'data': {
                'sqft': 2550,
                'bedrooms': 4,
                'bathrooms': 2.5,
                'location_tier': 'Suburban',
                'year_built': 2012,
                'garage_cars': 2,
                'school_rating': 8.2,
                'distance_to_city_center_km': 12.0,
                'lot_size_sqft': 6800,
                'renovated': 1
            }
        },
        {
            'id': 'urban',
            'name': '🏙️ Urban City Condo',
            'data': {
                'sqft': 1650,
                'bedrooms': 3,
                'bathrooms': 2.0,
                'location_tier': 'Urban',
                'year_built': 2020,
                'garage_cars': 1,
                'school_rating': 7.8,
                'distance_to_city_center_km': 3.5,
                'lot_size_sqft': 2200,
                'renovated': 0
            }
        },
        {
            'id': 'luxury',
            'name': '👑 Prime Luxury Estate',
            'data': {
                'sqft': 4800,
                'bedrooms': 5,
                'bathrooms': 4.5,
                'location_tier': 'Luxury',
                'year_built': 2022,
                'garage_cars': 3,
                'school_rating': 9.5,
                'distance_to_city_center_km': 4.0,
                'lot_size_sqft': 15000,
                'renovated': 1
            }
        }
    ]
    return jsonify(presets)

if __name__ == '__main__':
    print("[+] Starting House Price Prediction Flask Server on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
