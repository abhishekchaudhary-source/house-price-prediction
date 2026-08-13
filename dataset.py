import numpy as np
import pandas as pd
import os

def generate_housing_dataset(n_samples=1500, random_state=42):
    """
    Generates a realistic synthetic housing dataset with domain-accurate feature distributions,
    non-linear relationships, and market pricing patterns.
    """
    np.random.seed(random_state)
    
    # 1. Living area square footage (log-normal distribution)
    sqft = np.random.lognormal(mean=7.5, sigma=0.4, size=n_samples).astype(int)
    sqft = np.clip(sqft, 600, 6000)
    
    # 2. Bedrooms correlated with square footage
    bedrooms = np.round(1 + sqft / 700 + np.random.normal(0, 0.5, n_samples)).astype(int)
    bedrooms = np.clip(bedrooms, 1, 6)
    
    # 3. Bathrooms correlated with bedrooms and sqft
    bathrooms = np.round(0.5 + bedrooms * 0.7 + np.random.normal(0, 0.3, n_samples) * 2) / 2
    bathrooms = np.clip(bathrooms, 1.0, 5.0)
    
    # 4. Location Tier
    tiers = ['Budget', 'Suburban', 'Urban', 'Prime', 'Luxury']
    tier_probs = [0.20, 0.35, 0.25, 0.15, 0.05]
    location_tier = np.random.choice(tiers, size=n_samples, p=tier_probs)
    
    # Base price multiplier per location tier in Indian Rupees (₹/sqft)
    tier_base_sqft_price = {
        'Budget': 2200,
        'Suburban': 3500,     # ₹3,500 / sqft
        'Urban': 5500,
        'Prime': 8800,
        'Luxury': 15000
    }
    
    # 5. Year built (1950 to 2024)
    year_built = np.random.randint(1950, 2025, size=n_samples)
    current_year = 2025
    age = current_year - year_built
    
    # 6. Renovated flag (older houses more likely to be renovated)
    renovation_prob = np.where(age > 20, 0.35, 0.10)
    renovated = (np.random.rand(n_samples) < renovation_prob).astype(int)
    
    # 7. Garage space (cars)
    garage_cars = np.random.choice([0, 1, 2, 3, 4], size=n_samples, p=[0.10, 0.30, 0.45, 0.12, 0.03])
    
    # 8. School quality score (1.0 to 10.0)
    school_rating = np.round(np.random.beta(5, 2, size=n_samples) * 9 + 1, 1)
    
    # 9. Distance to city center (km)
    distance_to_city_center_km = np.round(np.random.exponential(scale=8.0, size=n_samples) + 0.5, 1)
    distance_to_city_center_km = np.clip(distance_to_city_center_km, 0.5, 40.0)
    
    # 10. Lot size in sqft (at least equal to sqft + yard)
    lot_size_sqft = sqft + np.random.exponential(scale=4000, size=n_samples).astype(int)
    lot_size_sqft = np.clip(lot_size_sqft, 1000, 30000)
    
    # Target Price Calculation (Realistic Indian Housing Formula)
    price = np.zeros(n_samples)
    
    for i in range(n_samples):
        base_rate = tier_base_sqft_price[location_tier[i]]
        
        # Base value from living space
        val = sqft[i] * base_rate
        
        # Bedroom & Bathroom adjustments in INR
        val += bedrooms[i] * 150000
        val += bathrooms[i] * 200000
        
        # Age depreciation vs renovation premium
        effective_age = age[i] * 0.4 if renovated[i] else age[i]
        age_multiplier = max(0.65, 1.0 - (effective_age * 0.004))
        val *= age_multiplier
        
        # School rating bonus (+0% to +18%)
        val *= (1.0 + (school_rating[i] - 5.0) * 0.02)
        
        # Proximity bonus/penalty
        proximity_factor = max(0.75, 1.15 - (distance_to_city_center_km[i] * 0.012))
        val *= proximity_factor
        
        # Garage bonus
        val += garage_cars[i] * 150000
        
        # Lot size bonus
        val += lot_size_sqft[i] * 50.0
        
        # Random market fluctuation (+/- 5%)
        noise = np.random.normal(1.0, 0.05)
        val *= noise
        
        price[i] = round(val, -4) # Round to nearest 10,000 INR
        
    df = pd.DataFrame({
        'sqft': sqft,
        'bedrooms': bedrooms,
        'bathrooms': bathrooms,
        'location_tier': location_tier,
        'year_built': year_built,
        'garage_cars': garage_cars,
        'school_rating': school_rating,
        'distance_to_city_center_km': distance_to_city_center_km,
        'lot_size_sqft': lot_size_sqft,
        'renovated': renovated,
        'price': price
    })
    
    return df

def save_dataset(filepath='housing_data.csv'):
    df = generate_housing_dataset()
    df.to_csv(filepath, index=False)
    print(f"[+] Dataset created successfully with {len(df)} records at {filepath}")
    return df

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    save_dataset(os.path.join(script_dir, 'housing_data.csv'))
