# """
# Latency Prediction Model Training

# Per ML-SPEC.md §1: Train a GBDT regression model to predict ESP delivery latency
# from (ESP, hour_of_day, day_of_week, payload_size, campaign_type, queue_depth).

# Usage:
#     python scripts/train_latency_model.py --output models/latency_model.pkl
# """

import argparse
import pickle
from datetime import datetime
from clickhouse_driver import Client
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def fetch_training_data(clickhouse_host='localhost', clickhouse_port=9000, min_samples=100):
    """Fetch latency telemetry from ClickHouse materialized view"""
    print(f"📊 Connecting to ClickHouse at {clickhouse_host}:{clickhouse_port}...")
    
    client = Client(
        host=clickhouse_host, 
        port=clickhouse_port, 
        database='sendflowr',
        user='sendflowr',
        password='sendflowr_dev'
    )
    
    query = """
    SELECT 
        esp,
        campaign_type,
        hour_of_day,
        minute,
        day_of_week,
        payload_size_bytes,
        queue_depth_estimate,
        latency_seconds
    FROM sendflowr.latency_training_mv
    WHERE latency_seconds IS NOT NULL
      AND latency_seconds > 0
      AND latency_seconds < 900
    ORDER BY timestamp DESC
    """
    
    print("🔍 Fetching training data from latency_training_mv...")
    result = client.execute(query)
    
    if len(result) < min_samples:
        raise ValueError(f"Insufficient training data: {len(result)} samples (minimum {min_samples} required)")
    
    df = pd.DataFrame(result, columns=[
        'esp', 'campaign_type', 'hour_of_day', 'minute', 
        'day_of_week', 'payload_size_bytes', 'queue_depth_estimate', 'latency_seconds'
    ])
    
    print(f"✅ Loaded {len(df)} training samples")
    print(f"   Latency range: {df['latency_seconds'].min():.1f}s - {df['latency_seconds'].max():.1f}s")
    print(f"   Mean latency: {df['latency_seconds'].mean():.1f}s")
    print(f"   Median latency: {df['latency_seconds'].median():.1f}s")
    
    return df


def engineer_features(df):
    """Create additional features for better predictions (multi-channel)"""
    
    # One-hot encode providers (email ESPs)
    df['esp_klaviyo'] = (df['esp'] == 'klaviyo').astype(int)
    df['esp_sendgrid'] = (df['esp'] == 'sendgrid').astype(int)
    df['esp_mailchimp'] = (df['esp'] == 'mailchimp').astype(int)
    
    # One-hot encode providers (SMS)
    df['esp_twilio'] = (df['esp'] == 'twilio').astype(int)
    df['esp_messagebird'] = (df['esp'] == 'messagebird').astype(int)
    
    # One-hot encode providers (Push)
    df['esp_onesignal'] = (df['esp'] == 'onesignal').astype(int)
    df['esp_firebase'] = (df['esp'] == 'firebase').astype(int)
    
    # One-hot encode campaign type
    df['campaign_transactional'] = (df['campaign_type'] == 'transactional').astype(int)
    df['campaign_promotional'] = (df['campaign_type'] == 'promotional').astype(int)
    
    # Top-of-hour flag (critical signal per ML-SPEC.md)
    df['is_top_of_hour'] = df['minute'].isin([0, 1, 2]).astype(int)
    df['is_quarter_hour'] = df['minute'].isin([15, 30, 45]).astype(int)
    
    # Rush hour flags
    df['is_morning_rush'] = df['hour_of_day'].isin([8, 9]).astype(int)
    df['is_evening_rush'] = df['hour_of_day'].isin([18, 19]).astype(int)
    
    # Weekend flag
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
    
    # Late night flag
    df['is_late_night'] = df['hour_of_day'].isin([0, 1, 2, 3, 4, 5]).astype(int)
    
    # Payload size in KB (normalized)
    df['payload_size_kb'] = df['payload_size_bytes'] / 1024
    df['payload_large'] = (df['payload_size_kb'] > 200).astype(int)
    
    # Queue depth categories
    df['queue_high'] = (df['queue_depth_estimate'] > 5000).astype(int)
    df['queue_medium'] = ((df['queue_depth_estimate'] > 1000) & (df['queue_depth_estimate'] <= 5000)).astype(int)
    
    return df


def train_model(df, test_size=0.2, random_state=42):
    """Train GBDT model for latency prediction"""
    
    # Feature columns (per ML-SPEC.md §1 - multi-channel)
    feature_cols = [
        # Providers (multi-channel: email, SMS, push)
        'esp_klaviyo', 'esp_sendgrid', 'esp_mailchimp',
        'esp_twilio', 'esp_messagebird',
        'esp_onesignal', 'esp_firebase',
        # Time features
        'hour_of_day', 'minute', 'day_of_week',
        'is_top_of_hour', 'is_quarter_hour',
        'is_morning_rush', 'is_evening_rush',
        'is_weekend', 'is_late_night',
        # Campaign
        'campaign_transactional', 'campaign_promotional',
        # Payload
        'payload_size_kb', 'payload_large',
        # Queue
        'queue_depth_estimate', 'queue_high', 'queue_medium'
    ]
    
    X = df[feature_cols]
    y = df['latency_seconds']
    
    print(f"\n🔧 Training GBDT model with {len(feature_cols)} features...")
    print(f"   Features: {', '.join(feature_cols[:5])}... ({len(feature_cols)} total)")
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )
    
    # Train Gradient Boosting model
    model = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        min_samples_split=20,
        min_samples_leaf=10,
        random_state=random_state,
        verbose=0
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)
    
    train_mae = mean_absolute_error(y_train, y_pred_train)
    test_mae = mean_absolute_error(y_test, y_pred_test)
    test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
    test_r2 = r2_score(y_test, y_pred_test)
    
    print(f"\n📈 Model Performance:")
    print(f"   Train MAE: {train_mae:.2f}s")
    print(f"   Test MAE:  {test_mae:.2f}s")
    print(f"   Test RMSE: {test_rmse:.2f}s")
    print(f"   Test R²:   {test_r2:.3f}")
    
    # Feature importance
    print(f"\n🎯 Top 10 Most Important Features:")
    feature_importance = sorted(
        zip(feature_cols, model.feature_importances_),
        key=lambda x: x[1],
        reverse=True
    )
    for feat, importance in feature_importance[:10]:
        print(f"   {feat:25s} {importance:.4f}")
    
    # Return model and metadata
    return {
        'model': model,
        'feature_cols': feature_cols,
        'train_samples': len(X_train),
        'test_samples': len(X_test),
        'test_mae': test_mae,
        'test_rmse': test_rmse,
        'test_r2': test_r2,
        'trained_at': datetime.utcnow().isoformat(),
        'version': '1.0'
    }


def save_model(model_data, output_path):
    """Save trained model to disk"""
    print(f"\n💾 Saving model to {output_path}...")
    
    with open(output_path, 'wb') as f:
        pickle.dump(model_data, f)
    
    print(f"✅ Model saved successfully")
    print(f"   File size: {len(pickle.dumps(model_data)) / 1024:.1f} KB")


def main():
    parser = argparse.ArgumentParser(description='Train ESP latency prediction model')
    parser.add_argument('--output', default='models/latency_model.pkl', help='Output model file path')
    parser.add_argument('--clickhouse-host', default='localhost', help='ClickHouse host')
    parser.add_argument('--clickhouse-port', type=int, default=9000, help='ClickHouse port')
    parser.add_argument('--min-samples', type=int, default=100, help='Minimum training samples required')
    
    args = parser.parse_args()
    
    print("🌸 SendFlowr Latency Model Training")
    print("=" * 50)
    print(f"Per ML-SPEC.md §1: Latency Prediction\n")
    
    # Fetch data
    df = fetch_training_data(
        clickhouse_host=args.clickhouse_host,
        clickhouse_port=args.clickhouse_port,
        min_samples=args.min_samples
    )
    
    # Engineer features
    print("\n🔨 Engineering features...")
    df = engineer_features(df)
    
    # Train model
    model_data = train_model(df)
    
    # Save model
    save_model(model_data, args.output)
    
    print("\n🎉 Training complete!")
    print(f"\nTo use this model in inference, update ml_models.py to load: {args.output}")


if __name__ == '__main__':
    main()
