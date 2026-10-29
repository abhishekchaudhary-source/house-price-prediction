import os
import sys
import json
import time
import hashlib
from flask import Flask, render_template, jsonify, request
from pydantic import ValidationError

from models import PureNumPyPipeline
sys.modules['__main__'].PureNumPyPipeline = PureNumPyPipeline

from predict import HousePricePredictor
from train_model import train_and_evaluate_models
from schemas import HousePredictionRequest, LeadCaptureRequest
from database import init_db, log_prediction, save_lead, get_analytics_summary

# Flask-Limiter for API Rate Limiting
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    HAS_LIMITER = True
except ImportError:
    HAS_LIMITER = False

app = Flask(__name__, template_folder='templates', static_folder='static')

# Initialize Database
init_db()

# Initialize Rate Limiter (60 requests/min per IP on prediction, 200/min overall)
if HAS_LIMITER:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["300 per minute", "20 per second"],
        storage_uri="memory://",
    )
else:
    class DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(f): return f
            return decorator
    limiter = DummyLimiter()

# Initialize Predictor (or train if needed)
script_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(script_dir, 'best_house_price_model.joblib')

if not os.path.exists(model_path):
    print("[*] Model not found on server start. Training model...")
    train_and_evaluate_models()

predictor = HousePricePredictor()

# --- SECURITY HEADERS MIDDLEWARE ---
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Server'] = 'EstimatorAI-Production/2.0'
    return response

# --- ERROR HANDLERS ---
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        'status': 'error',
        'code': 429,
        'message': 'Rate limit exceeded. Please wait a moment before trying again.'
    }), 429

@app.errorhandler(404)
def not_found_handler(e):
    if request.path.startswith('/api/'):
        return jsonify({'status': 'error', 'code': 404, 'message': 'API endpoint not found'}), 404
    return render_template('index.html'), 404

@app.errorhandler(500)
def server_error_handler(e):
    return jsonify({
        'status': 'error',
        'code': 500,
        'message': 'Internal server error occurred.'
    }), 500

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/predict', methods=['POST'])
@limiter.limit("60 per minute")
def api_predict():
    start_time = time.time()
    raw_json = request.get_json(silent=True)
    if not raw_json:
        return jsonify({
            'status': 'error',
            'code': 400,
            'message': 'No JSON payload provided in request body.'
        }), 400

    # 1. Pydantic Strict Validation & Sanitization
    try:
        validated_input = HousePredictionRequest(**raw_json)
    except ValidationError as err:
        errors = []
        for e in err.errors():
            loc = " -> ".join([str(x) for x in e['loc']])
            errors.append(f"{loc}: {e['msg']}")
        return jsonify({
            'status': 'error',
            'code': 422,
            'message': 'Input validation failed',
            'validation_errors': errors
        }), 422

    # 2. Run Model Inference
    try:
        payload_dict = validated_input.model_dump()
        result = predictor.predict(payload_dict)
        latency_ms = round((time.time() - start_time) * 1000, 2)
        result['latency_ms'] = latency_ms

        # 3. Log Prediction to Database (Asynchronously/Safe)
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')
        ip_hash = hashlib.sha256(client_ip.encode('utf-8')).hexdigest()[:16]

        log_prediction(
            ip_hash=ip_hash,
            locality=validated_input.locality,
            location_tier=validated_input.location_tier,
            sqft=validated_input.sqft,
            bedrooms=validated_input.bedrooms,
            bathrooms=validated_input.bathrooms,
            distance_km=validated_input.distance_to_city_center_km,
            predicted_price=result['predicted_price'],
            price_per_sqft=result['price_per_sqft'],
            latency_ms=latency_ms
        )

        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'code': 500, 'message': str(e)}), 500

@app.route('/api/lead', methods=['POST'])
@limiter.limit("15 per hour")
def api_lead():
    raw_json = request.get_json(silent=True)
    if not raw_json:
        return jsonify({'status': 'error', 'code': 400, 'message': 'Invalid lead payload'}), 400

    try:
        validated_lead = LeadCaptureRequest(**raw_json)
        lead_id = save_lead(
            name=validated_lead.name,
            phone=validated_lead.phone,
            email=validated_lead.email,
            locality=validated_lead.locality,
            property_sqft=validated_lead.property_sqft,
            estimated_price=validated_lead.estimated_price
        )
        return jsonify({
            'status': 'success',
            'lead_id': lead_id,
            'message': 'Thank you! Your valuation inquiry has been recorded.'
        }), 201
    except ValidationError as err:
        errors = [f"{' -> '.join(str(x) for x in e['loc'])}: {e['msg']}" for e in err.errors()]
        return jsonify({'status': 'error', 'code': 422, 'validation_errors': errors}), 422
    except Exception as e:
        return jsonify({'status': 'error', 'code': 500, 'message': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def api_stats():
    try:
        stats = get_analytics_summary()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def api_health():
    return jsonify({
        'status': 'healthy',
        'service': 'house-price-prediction-engine',
        'model_loaded': predictor is not None,
        'best_model': predictor.best_model_name,
        'model_r2': predictor.r2,
        'timestamp': time.time()
    })

@app.route('/api/metadata', methods=['GET'])
def api_metadata():
    try:
        meta_path = os.path.join(script_dir, 'model_metadata.json')
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        return jsonify(meta)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

BANGALORE_LOCALITIES = [
    {"name": "Indiranagar", "lat": 12.9784, "lng": 77.6408, "dist": 4.5, "tier": "Luxury", "desc": "Prime Tech, Boutique & Dining Hub"},
    {"name": "Koramangala", "lat": 12.9352, "lng": 77.6245, "dist": 6.5, "tier": "Luxury", "desc": "Startup & High-Net-Worth Residential Capital"},
    {"name": "Rajaji Nagar", "lat": 12.9982, "lng": 77.5530, "dist": 6.0, "tier": "Luxury", "desc": "Historic West Bangalore Commercial & Elite Center"},
    {"name": "Malleshwaram", "lat": 13.0031, "lng": 77.5643, "dist": 5.5, "tier": "Luxury", "desc": "Cultural Heritage & Upscale Residential"},
    {"name": "Frazer Town", "lat": 12.9968, "lng": 77.6130, "dist": 3.5, "tier": "Luxury", "desc": "Central Heritage Cantonment Area"},
    {"name": "Hebbal", "lat": 13.0358, "lng": 77.5970, "dist": 11.0, "tier": "Prime", "desc": "North Bangalore Tech Corridor & Lake Hub"},
    {"name": "7th Phase JP Nagar", "lat": 12.8943, "lng": 77.5857, "dist": 10.0, "tier": "Prime", "desc": "South Bangalore Lush Residential Hub"},
    {"name": "Bellandur", "lat": 12.9304, "lng": 77.6784, "dist": 13.0, "tier": "Prime", "desc": "Outer Ring Road IT Tech Park Hub"},
    {"name": "Hennur Road", "lat": 13.0360, "lng": 77.6390, "dist": 12.0, "tier": "Prime", "desc": "Airport Link & Fast-Appreciating Zone"},
    {"name": "Whitefield", "lat": 12.9698, "lng": 77.7499, "dist": 18.5, "tier": "Urban", "desc": "Major Global IT Corridor & Tech Parks"},
    {"name": "Sarjapur Road", "lat": 12.9237, "lng": 77.6705, "dist": 17.5, "tier": "Urban", "desc": "Rapidly Growing Tech & Villa Corridor"},
    {"name": "Marathahalli", "lat": 12.9591, "lng": 77.6974, "dist": 14.0, "tier": "Urban", "desc": "East Bangalore Transit & Tech Zone"},
    {"name": "Thanisandra", "lat": 13.0543, "lng": 77.6329, "dist": 13.5, "tier": "Urban", "desc": "Manyata Tech Park North Hub"},
    {"name": "Kanakpura Road", "lat": 12.8988, "lng": 77.5501, "dist": 15.0, "tier": "Urban", "desc": "Green Metro Connected Corridor"},
    {"name": "Bannerghatta Road", "lat": 12.8910, "lng": 77.5970, "dist": 13.0, "tier": "Urban", "desc": "IIMB & Healthcare Hub Corridor"},
    {"name": "Electronic City", "lat": 12.8452, "lng": 77.6602, "dist": 19.0, "tier": "Suburban", "desc": "Infosys & Wipro Tech Giant Hub"},
    {"name": "Yelahanka", "lat": 13.1007, "lng": 77.5963, "dist": 17.0, "tier": "Suburban", "desc": "North Bangalore Airport Gateway & Township"},
    {"name": "Uttarahalli", "lat": 12.9056, "lng": 77.5348, "dist": 13.0, "tier": "Suburban", "desc": "Peaceful Residential South-West Suburb"},
    {"name": "Raja Rajeshwari Nagar", "lat": 12.9274, "lng": 77.5154, "dist": 12.5, "tier": "Suburban", "desc": "Temple Hill & Suburban Tech Enclave"},
    {"name": "Chandapura", "lat": 12.7937, "lng": 77.7022, "dist": 26.0, "tier": "Budget", "desc": "Affordable Industrial & Residential Growth Area"},
    {"name": "Electronic City Phase II", "lat": 12.8340, "lng": 77.6780, "dist": 21.0, "tier": "Budget", "desc": "Affordable IT Housing Corridor"},
    {"name": "Attibele", "lat": 12.7783, "lng": 77.7717, "dist": 32.0, "tier": "Budget", "desc": "Border Industrial Affordable Housing Hub"}
]

@app.route('/api/localities', methods=['GET'])
def api_localities():
    return jsonify(BANGALORE_LOCALITIES)

@app.route('/api/presets', methods=['GET'])
def api_presets():
    presets = [
        {
            'id': 'starter',
            'name': '🏡 Starter 2BHK (Electronic City)',
            'data': {
                'sqft': 1056,
                'bedrooms': 2,
                'bathrooms': 2.0,
                'location_tier': 'Suburban',
                'year_built': 2016,
                'garage_cars': 1,
                'school_rating': 7.2,
                'distance_to_city_center_km': 19.0,
                'lot_size_sqft': 2200,
                'renovated': 0,
                'locality': 'Electronic City'
            }
        },
        {
            'id': 'tech_corridor',
            'name': '🌳 Tech Villa (Whitefield / Sarjapur)',
            'data': {
                'sqft': 2150,
                'bedrooms': 3,
                'bathrooms': 3.0,
                'location_tier': 'Urban',
                'year_built': 2020,
                'garage_cars': 2,
                'school_rating': 8.5,
                'distance_to_city_center_km': 18.5,
                'lot_size_sqft': 4200,
                'renovated': 0,
                'locality': 'Whitefield'
            }
        },
        {
            'id': 'prime_condo',
            'name': '🏙️ Prime Lakeview (Hebbal / JP Nagar)',
            'data': {
                'sqft': 2600,
                'bedrooms': 3,
                'bathrooms': 3.5,
                'location_tier': 'Prime',
                'year_built': 2022,
                'garage_cars': 2,
                'school_rating': 9.0,
                'distance_to_city_center_km': 11.0,
                'lot_size_sqft': 5400,
                'renovated': 1,
                'locality': 'Hebbal'
            }
        },
        {
            'id': 'luxury_estate',
            'name': '👑 Elite Penthouse (Koramangala / Indiranagar)',
            'data': {
                'sqft': 3800,
                'bedrooms': 4,
                'bathrooms': 4.5,
                'location_tier': 'Luxury',
                'year_built': 2023,
                'garage_cars': 3,
                'school_rating': 9.6,
                'distance_to_city_center_km': 6.5,
                'lot_size_sqft': 8500,
                'renovated': 1,
                'locality': 'Koramangala'
            }
        }
    ]
    return jsonify(presets)

if __name__ == '__main__':
    print("[+] Starting House Price Prediction Production Server on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
