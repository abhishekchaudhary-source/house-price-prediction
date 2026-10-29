import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Text, func
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class PredictionLog(Base):
    __tablename__ = 'prediction_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    ip_hash = Column(String(64), nullable=True)
    locality = Column(String(120), nullable=True)
    location_tier = Column(String(50), nullable=False)
    sqft = Column(Integer, nullable=False)
    bedrooms = Column(Integer, nullable=False)
    bathrooms = Column(Float, nullable=False)
    distance_km = Column(Float, nullable=False)
    predicted_price = Column(Float, nullable=False)
    price_per_sqft = Column(Float, nullable=False)
    latency_ms = Column(Float, nullable=False)

class ValuationLead(Base):
    __tablename__ = 'valuation_leads'

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(120), nullable=False)
    locality = Column(String(120), nullable=True)
    property_sqft = Column(Integer, nullable=True)
    estimated_price = Column(Float, nullable=True)

# Database Setup
script_dir = os.path.dirname(os.path.abspath(__file__))
default_db_path = os.path.join(script_dir, 'house_predictions.db')
DATABASE_URL = os.environ.get('DATABASE_URL', f'sqlite:///{default_db_path}')

# Engine configuration (PostgreSQL vs SQLite)
if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
else:
    engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    print(f"[✓] Database initialized with engine: {engine.name}")

def log_prediction(ip_hash, locality, location_tier, sqft, bedrooms, bathrooms, distance_km, predicted_price, price_per_sqft, latency_ms):
    session = SessionLocal()
    try:
        record = PredictionLog(
            ip_hash=ip_hash,
            locality=locality,
            location_tier=location_tier,
            sqft=sqft,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            distance_km=distance_km,
            predicted_price=predicted_price,
            price_per_sqft=price_per_sqft,
            latency_ms=latency_ms
        )
        session.add(record)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[!] Warning: Failed to log prediction: {e}")
    finally:
        session.close()

def save_lead(name, phone, email, locality=None, property_sqft=None, estimated_price=None):
    session = SessionLocal()
    try:
        lead = ValuationLead(
            name=name,
            phone=phone,
            email=email,
            locality=locality,
            property_sqft=property_sqft,
            estimated_price=estimated_price
        )
        session.add(lead)
        session.commit()
        lead_id = lead.id
        return lead_id
    except Exception as e:
        session.rollback()
        print(f"[!] Error saving lead: {e}")
        raise e
    finally:
        session.close()

def get_analytics_summary():
    session = SessionLocal()
    try:
        total_predictions = session.query(func.count(PredictionLog.id)).scalar() or 0
        avg_price = session.query(func.avg(PredictionLog.predicted_price)).scalar() or 0.0
        total_leads = session.query(func.count(ValuationLead.id)).scalar() or 0
        
        # Most popular locality
        top_locality = session.query(
            PredictionLog.locality, func.count(PredictionLog.id).label('cnt')
        ).filter(PredictionLog.locality.isnot(None)).group_by(PredictionLog.locality).order_by(func.count(PredictionLog.id).desc()).first()

        return {
            'total_predictions_served': total_predictions,
            'average_valuation_inr': round(float(avg_price), 2),
            'total_inquiries_captured': total_leads,
            'most_active_locality': top_locality[0] if top_locality else 'Whitefield'
        }
    finally:
        session.close()
