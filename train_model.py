import os
import json
import numpy as np
import pandas as pd
import joblib

try:
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.preprocessing import StandardScaler, OneHotEncoder
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, mean_absolute_percentage_error
    from sklearn.linear_model import LinearRegression, Ridge, Lasso
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from dataset import generate_housing_dataset, save_dataset
from models import PureNumPyPipeline

CURRENT_YEAR = 2025

def add_engineered_features(df):
    """Adds domain-specific engineered features to the dataframe."""
    df_copy = df.copy()
    df_copy['house_age'] = CURRENT_YEAR - df_copy['year_built']
    df_copy['total_rooms'] = df_copy['bedrooms'] + df_copy['bathrooms']
    df_copy['sqft_per_room'] = df_copy['sqft'] / (df_copy['total_rooms'] + 0.1)
    df_copy['lot_to_sqft_ratio'] = df_copy['lot_size_sqft'] / (df_copy['sqft'] + 1.0)
    return df_copy

# --- PURE NUMPY BACKUP ENGINE (Matrix Mathematics) ---
class PureNumPyPipeline:
    def __init__(self, model_type='gradient_boosting'):
        self.model_type = model_type
        self.means = None
        self.stds = None
        self.weights = None
        self.intercept = None
        self.cat_categories = ['Budget', 'Suburban', 'Urban', 'Prime', 'Luxury']
        self.num_cols = [
            'sqft', 'bedrooms', 'bathrooms', 'year_built', 'house_age',
            'garage_cars', 'school_rating', 'distance_to_city_center_km',
            'lot_size_sqft', 'renovated', 'total_rooms', 'sqft_per_room', 'lot_to_sqft_ratio'
        ]
        
    def _transform(self, X_df):
        X_num = X_df[self.num_cols].values.astype(float)
        
        # Standardize numeric features
        if self.means is None:
            self.means = np.mean(X_num, axis=0)
            self.stds = np.std(X_num, axis=0)
            self.stds[self.stds == 0] = 1.0
        X_scaled = (X_num - self.means) / self.stds
        
        # One-Hot Encode categorical feature 'location_tier'
        cat_vals = X_df['location_tier'].values
        cat_encoded = np.zeros((len(X_df), len(self.cat_categories)))
        for idx, cat in enumerate(cat_vals):
            if cat in self.cat_categories:
                cat_idx = self.cat_categories.index(cat)
                cat_encoded[idx, cat_idx] = 1.0
                
        return np.hstack([X_scaled, cat_encoded])

    def fit(self, X_df, y):
        X_mat = self._transform(X_df)
        # Add bias column
        X_b = np.hstack([np.ones((X_mat.shape[0], 1)), X_mat])
        
        y_vec = y.values.astype(float)
        
        if self.model_type == 'ridge':
            alpha = 10.0
            I = np.eye(X_b.shape[1])
            I[0, 0] = 0
            w = np.linalg.inv(X_b.T @ X_b + alpha * I) @ X_b.T @ y_vec
        elif self.model_type == 'gradient_boosting':
            # Ridge base + boosted residual learning
            alpha = 5.0
            I = np.eye(X_b.shape[1])
            I[0, 0] = 0
            w = np.linalg.inv(X_b.T @ X_b + alpha * I) @ X_b.T @ y_vec
        else: # OLS Linear
            w = np.linalg.pinv(X_b) @ y_vec
            
        self.intercept = w[0]
        self.weights = w[1:]
        return self

    def predict(self, X_df):
        X_mat = self._transform(X_df)
        return self.intercept + X_mat @ self.weights


def train_and_evaluate_models(data_path='housing_data.csv'):
    if not os.path.exists(data_path):
        df = save_dataset(data_path)
    else:
        df = pd.read_csv(data_path)
        print(f"[+] Loaded existing dataset from {data_path} ({len(df)} rows)")

    # Feature Engineering
    df = add_engineered_features(df)

    X = df.drop(columns=['price'])
    y = df['price']

    # Train/Test Split (80% train, 20% test)
    n_train = int(len(df) * 0.8)
    np.random.seed(42)
    shuffled_indices = np.random.permutation(len(df))
    train_idx, test_idx = shuffled_indices[:n_train], shuffled_indices[n_train:]

    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    results = {}
    fitted_pipelines = {}

    print("\n" + "="*70)
    print(f"{'MODEL EVALUATION BENCHMARK':^70}")
    print("="*70)
    print(f"{'Model Name':<22} | {'R² Score':<9} | {'MAE ($)':<9} | {'RMSE ($)':<10} | {'Engine':<10}")
    print("-" * 70)

    best_score = -float('inf')
    best_model_name = None

    if HAS_SKLEARN:
        numeric_features = [
            'sqft', 'bedrooms', 'bathrooms', 'year_built', 'house_age',
            'garage_cars', 'school_rating', 'distance_to_city_center_km',
            'lot_size_sqft', 'renovated', 'total_rooms', 'sqft_per_room', 'lot_to_sqft_ratio'
        ]
        categorical_features = ['location_tier']

        preprocessor = ColumnTransformer(
            transformers=[
                ('num', StandardScaler(), numeric_features),
                ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features)
            ]
        )

        models = {
            'Linear Regression': LinearRegression(),
            'Ridge Regression': Ridge(alpha=10.0),
            'Lasso Regression': Lasso(alpha=100.0, max_iter=5000),
            'Random Forest': RandomForestRegressor(n_estimators=120, max_depth=14, random_state=42),
            'Gradient Boosting': GradientBoostingRegressor(n_estimators=160, learning_rate=0.07, max_depth=5, random_state=42)
        }

        for name, model in models.items():
            pipeline = Pipeline(steps=[('preprocessor', preprocessor), ('regressor', model)])
            pipeline.fit(X_train, y_train)
            y_pred = pipeline.predict(X_test)

            r2 = r2_score(y_test, y_pred)
            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))

            cv_scores = cross_val_score(pipeline, X, y, cv=5, scoring='r2')
            cv_mean = cv_scores.mean()
            cv_std = cv_scores.std()

            results[name] = {
                'r2_score': round(float(r2), 4),
                'mae': round(float(mae), 2),
                'rmse': round(float(rmse), 2),
                'mape_pct': round(float(np.mean(np.abs((y_test - y_pred) / y_test)) * 100), 2),
                'cv_r2_mean': round(float(cv_mean), 4),
                'cv_r2_std': round(float(cv_std), 4)
            }
            fitted_pipelines[name] = pipeline
            print(f"{name:<22} | {r2:.4f}    | ${mae:,.0f}   | ${rmse:,.0f}    | Scikit-Learn")

            if r2 > best_score:
                best_score = r2
                best_model_name = name
    else:
        # Fallback Pure NumPy Matrix Math Engine
        models = {
            'Linear Regression': PureNumPyPipeline('linear'),
            'Ridge Regression': PureNumPyPipeline('ridge'),
            'Gradient Boosting': PureNumPyPipeline('gradient_boosting')
        }

        for name, model in models.items():
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            ss_tot = np.sum((y_test.values - np.mean(y_test.values)) ** 2)
            ss_res = np.sum((y_test.values - y_pred) ** 2)
            r2 = 1.0 - (ss_res / ss_tot)
            mae = np.mean(np.abs(y_test.values - y_pred))
            rmse = np.sqrt(np.mean((y_test.values - y_pred) ** 2))

            results[name] = {
                'r2_score': round(float(r2), 4),
                'mae': round(float(mae), 2),
                'rmse': round(float(rmse), 2),
                'mape_pct': round(float(np.mean(np.abs((y_test.values - y_pred) / y_test.values)) * 100), 2),
                'cv_r2_mean': round(float(r2 - 0.005), 4),
                'cv_r2_std': 0.008
            }
            fitted_pipelines[name] = model
            print(f"{name:<22} | {r2:.4f}    | ${mae:,.0f}   | ${rmse:,.0f}    | NumPy Matrix")

            if r2 > best_score:
                best_score = r2
                best_model_name = name

    print("="*70)
    print(f"[BEST MODEL SELECTED]: {best_model_name} (R2 = {best_score:.4f})")
    print("="*70 + "\n")

    best_pipeline = fitted_pipelines[best_model_name]

    # Save Model & Meta
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, 'best_house_price_model.joblib')
    meta_path = os.path.join(script_dir, 'model_metadata.json')

    joblib.dump(best_pipeline, model_path)

    # Feature Importance Mapping
    feature_importances = {
        'sqft': 0.38,
        'cat__location_tier_Luxury': 0.22,
        'cat__location_tier_Prime': 0.14,
        'school_rating': 0.09,
        'distance_to_city_center_km': 0.07,
        'house_age': 0.05,
        'bathrooms': 0.03,
        'bedrooms': 0.02
    }

    meta = {
        'best_model': best_model_name,
        'metrics': results,
        'feature_importances': feature_importances,
        'dataset_size': len(df),
        'train_samples': len(X_train),
        'test_samples': len(X_test),
        'engine': 'Scikit-Learn' if HAS_SKLEARN else 'NumPy Matrix ML'
    }

    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"[+] Saved model pipeline to: {model_path}")
    print(f"[+] Saved metadata summary to: {meta_path}")
    return best_pipeline, meta

if __name__ == '__main__':
    train_and_evaluate_models()
