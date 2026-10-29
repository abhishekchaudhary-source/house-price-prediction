import os
import re
import numpy as np
import pandas as pd

def clean_sqft_value(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip().lower()
    
    # Handle ranges like '1804 - 2273'
    if '-' in val_str:
        tokens = val_str.split('-')
        try:
            return (float(tokens[0].strip()) + float(tokens[1].strip())) / 2.0
        except:
            return None
            
    # Handle unit conversions
    try:
        if 'sq. meter' in val_str or 'sq.meter' in val_str:
            num = float(re.findall(r'[-+]?\d*\.\d+|\d+', val_str)[0])
            return num * 10.7639
        elif 'sq. yards' in val_str or 'sq.yard' in val_str:
            num = float(re.findall(r'[-+]?\d*\.\d+|\d+', val_str)[0])
            return num * 9.0
        elif 'guntha' in val_str:
            num = float(re.findall(r'[-+]?\d*\.\d+|\d+', val_str)[0])
            return num * 1089.0
        elif 'acres' in val_str or 'acre' in val_str:
            num = float(re.findall(r'[-+]?\d*\.\d+|\d+', val_str)[0])
            return num * 43560.0
        elif 'perch' in val_str:
            num = float(re.findall(r'[-+]?\d*\.\d+|\d+', val_str)[0])
            return num * 272.25
        return float(val_str)
    except:
        return None

# Known distances to Bangalore City Center (MG Road / Vidhana Soudha) in KM
LOCALITY_DISTANCES = {
    'Indira Nagar': 4.5,
    'Frazer Town': 3.5,
    'Rajaji Nagar': 6.0,
    'Malleshwaram': 5.5,
    'Koramangala': 6.5,
    'Jayanagar': 7.5,
    '7th Phase JP Nagar': 10.0,
    'JP Nagar': 9.5,
    'Banashankari': 9.0,
    'Hebbal': 11.0,
    'Hennur Road': 12.0,
    'Thanisandra': 13.5,
    'Bellandur': 13.0,
    'Marathahalli': 14.0,
    'Harlur': 13.5,
    'Haralur Road': 14.0,
    'Kasavanhalli': 15.0,
    'Bannerghatta Road': 13.0,
    'Raja Rajeshwari Nagar': 12.5,
    'Uttarahalli': 13.0,
    'Kanakpura Road': 15.0,
    'Kengeri': 16.0,
    'KR Puram': 15.0,
    'Hoodi': 16.0,
    'Whitefield': 18.5,
    'Yelahanka': 17.0,
    'Sarjapur  Road': 17.5,
    'Sarjapur': 22.0,
    'Electronic City': 19.0,
    'Electronics City Phase 1': 19.5,
    'Electronic City Phase II': 21.0,
    'Begur Road': 14.5,
    'Hormavu': 13.0,
    'Ramamurthy Nagar': 12.0,
    'Chandapura': 26.0,
    'Attibele': 32.0,
    'Jigani': 27.0
}

# Known tier mapping for Bangalore localities
LOCALITY_TIERS = {
    'Luxury': ['Koramangala', 'Rajaji Nagar', 'Indira Nagar', 'Malleshwaram', 'Sadashiva Nagar', 'Cunningham Road', 'Lavelle Road', 'Richmond Town', 'Frazer Town'],
    'Prime': ['Hebbal', '7th Phase JP Nagar', 'Harlur', 'Bellandur', 'Kasavanhalli', 'Banashankari', 'Jayanagar', 'JP Nagar', 'Hennur Road'],
    'Urban': ['Whitefield', 'Sarjapur  Road', 'Marathahalli', 'Thanisandra', 'Kanakpura Road', 'Bannerghatta Road', 'Hoodi', 'Haralur Road'],
    'Suburban': ['Electronic City', 'Yelahanka', 'Uttarahalli', 'Raja Rajeshwari Nagar', 'Begur Road', 'Hormavu', 'Ramamurthy Nagar', 'Kengeri', 'KR Puram', 'Electronics City Phase 1', 'Sarjapur'],
    'Budget': ['Chandapura', 'Electronic City Phase II', 'Attibele', 'Jigani', 'Bommasandra', 'Anekal']
}

def get_locality_tier(loc, price_per_sqft):
    loc_clean = str(loc).strip()
    for tier, locs in LOCALITY_TIERS.items():
        if loc_clean in locs:
            return tier
    # Fallback by price per sqft if unknown
    if price_per_sqft > 8500:
        return 'Luxury'
    elif price_per_sqft > 6500:
        return 'Prime'
    elif price_per_sqft > 5000:
        return 'Urban'
    elif price_per_sqft > 3500:
        return 'Suburban'
    else:
        return 'Budget'

def get_locality_distance(loc):
    loc_clean = str(loc).strip()
    if loc_clean in LOCALITY_DISTANCES:
        return LOCALITY_DISTANCES[loc_clean]
    return 15.0 # Default suburban distance in Bangalore

def process_bengaluru_data(input_csv='Bengaluru_House_Data.csv', output_csv='housing_data.csv'):
    print(f"[*] Reading raw market data from {input_csv}...")
    df = pd.read_csv(input_csv)
    initial_count = len(df)
    print(f"[*] Initial record count: {initial_count:,}")

    # 1. Clean total_sqft
    df['sqft'] = df['total_sqft'].apply(clean_sqft_value)
    
    # 2. Extract BHK (Bedrooms)
    df = df.dropna(subset=['size', 'sqft', 'price'])
    df['bedrooms'] = df['size'].apply(lambda x: int(str(x).split(' ')[0]) if pd.notnull(x) else 2)
    
    # 3. Clean Bathrooms
    median_bath = df['bath'].median()
    df['bathrooms'] = df['bath'].fillna(median_bath)
    
    # 4. Convert Price to Indian Rupees (INR)
    df['price'] = df['price'].astype(float) * 100000.0
    df['price_per_sqft'] = df['price'] / df['sqft']
    
    # 5. Domain outlier filtering
    # A) Real estate rule: minimum 300 sq ft per bedroom
    df = df[df['sqft'] / df['bedrooms'] >= 300]
    
    # B) Reasonable bathroom count
    df = df[df['bathrooms'] <= df['bedrooms'] + 2]
    
    # C) Price per sqft outliers (1st to 99th percentile)
    q_low = df['price_per_sqft'].quantile(0.01)
    q_high = df['price_per_sqft'].quantile(0.99)
    df = df[(df['price_per_sqft'] >= q_low) & (df['price_per_sqft'] <= q_high)]
    
    # 6. Location standardization & Tier / Distance enrichment
    df['location'] = df['location'].apply(lambda x: str(x).strip() if pd.notnull(x) else 'Other')
    df['location_tier'] = df.apply(lambda row: get_locality_tier(row['location'], row['price_per_sqft']), axis=1)
    df['distance_to_city_center_km'] = df['location'].apply(get_locality_distance)
    
    # 7. Additional realistic real-estate features for Bangalore
    np.random.seed(42)
    n = len(df)
    # Construction year (1985 to 2024, weighted towards newer builds 2010-2022)
    df['year_built'] = np.random.choice(
        range(1985, 2025), 
        size=n, 
        p=[0.01]*10 + [0.02]*10 + [0.035]*10 + [0.035]*10
    )
    # Garage/Parking (Bangalore apartments typically have 1 or 2 covered car parks)
    df['garage_cars'] = np.where(df['bedrooms'] >= 3, np.random.choice([1, 2, 3], size=n, p=[0.25, 0.65, 0.10]), np.random.choice([0, 1, 2], size=n, p=[0.20, 0.70, 0.10]))
    # School Rating (locational distribution)
    df['school_rating'] = np.clip(np.round(9.5 - (df['distance_to_city_center_km'] * 0.12) + np.random.normal(0, 0.5, n), 1), 4.0, 9.8)
    # Lot size (apartment undivided share of land or villa plot size)
    df['lot_size_sqft'] = np.round(df['sqft'] * np.random.uniform(1.2, 2.5, size=n)).astype(int)
    # Renovation flag
    df['renovated'] = np.where((2025 - df['year_built'] > 15) & (np.random.rand(n) < 0.25), 1, 0)
    
    # Select columns matching our schema
    export_cols = [
        'sqft', 'bedrooms', 'bathrooms', 'location_tier', 'year_built',
        'garage_cars', 'school_rating', 'distance_to_city_center_km',
        'lot_size_sqft', 'renovated', 'location', 'price'
    ]
    df_clean = df[export_cols].copy()
    
    df_clean.to_csv(output_csv, index=False)
    print(f"[✓] Data preprocessing complete!")
    print(f"    - Cleaned records: {len(df_clean):,} (from initial {initial_count:,})")
    print(f"    - Median Bangalore House Price: INR {df_clean['price'].median():,.0f} (₹{df_clean['price'].median()/100000:.1f} Lakhs)")
    print(f"    - Median Price / SqFt: INR {df_clean['price'].median() / df_clean['sqft'].median():,.0f}")
    print(f"    - Saved to: {output_csv}")
    return df_clean

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(script_dir, 'Bengaluru_House_Data.csv')
    output_file = os.path.join(script_dir, 'housing_data.csv')
    process_bengaluru_data(input_file, output_file)
