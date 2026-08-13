import numpy as np

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
            alpha = 5.0
            I = np.eye(X_b.shape[1])
            I[0, 0] = 0
            w = np.linalg.inv(X_b.T @ X_b + alpha * I) @ X_b.T @ y_vec
        else: # OLS Linear
            w = np.linalg.pinv(X_b) @ y_vec
            
        self.intercept = float(w[0])
        self.weights = w[1:]
        return self

    def predict(self, X_df):
        X_mat = self._transform(X_df)
        preds = self.intercept + X_mat @ self.weights
        return np.asarray(preds).flatten()
