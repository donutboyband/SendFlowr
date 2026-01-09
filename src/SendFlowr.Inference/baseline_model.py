import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import json

class BaselineModel:
    """Baseline probabilistic model using hourly histograms"""
    
    def __init__(self):
        self.name = "baseline_v1"
    
    def predict_engagement_curve(
        self,
        hour_histogram: Dict[int, float],
        weekday_histogram: Dict[int, float],
        send_time: datetime,
        hours_ahead: int = 24
    ) -> List[Tuple[datetime, float]]:
        """
        Generate probability curve for the next N hours
        
        Returns list of (timestamp, probability) tuples
        """
        curve = []
        current_time = send_time
        
        for hour_offset in range(hours_ahead):
            future_time = current_time + timedelta(hours=hour_offset)
            hour_of_day = future_time.hour
            day_of_week = future_time.weekday()
            
            # Combine hourly and weekday signals
            hour_prob = hour_histogram.get(hour_of_day, 1.0/24.0)
            weekday_prob = weekday_histogram.get(day_of_week, 1.0/7.0)
            
            # Simple weighted average (can be improved with learned weights)
            combined_prob = 0.7 * hour_prob + 0.3 * weekday_prob
            
            curve.append((future_time, combined_prob))
        
        # Normalize to sum to 1.0
        total_prob = sum(p for _, p in curve)
        if total_prob > 0:
            curve = [(t, p / total_prob) for t, p in curve]
        
        return curve
    
    def find_optimal_send_window(
        self,
        curve: List[Tuple[datetime, float]],
        window_size_hours: int = 2,
        top_k: int = 3
    ) -> List[Tuple[datetime, datetime, float]]:
        """
        Find optimal send windows
        
        Returns list of (window_start, window_end, avg_probability) tuples
        """
        windows = []
        
        for i in range(len(curve) - window_size_hours + 1):
            window_slice = curve[i:i + window_size_hours]
            avg_prob = np.mean([p for _, p in window_slice])
            
            start_time = window_slice[0][0]
            end_time = window_slice[-1][0]
            
            windows.append((start_time, end_time, avg_prob))
        
        # Sort by average probability and return top K
        windows.sort(key=lambda x: x[2], reverse=True)
        return windows[:top_k]
    
    def explain_prediction(
        self,
        hour_histogram: Dict[int, float],
        weekday_histogram: Dict[int, float]
    ) -> Dict:
        """Generate human-readable explanation of the prediction"""
        
        # Find peak hours
        peak_hours = sorted(hour_histogram.items(), key=lambda x: x[1], reverse=True)[:3]
        peak_days = sorted(weekday_histogram.items(), key=lambda x: x[1], reverse=True)[:3]
        
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        return {
            'peak_hours': [
                {
                    'hour': hour,
                    'time': f"{hour:02d}:00-{(hour+1)%24:02d}:00",
                    'probability': round(prob * 100, 1)
                }
                for hour, prob in peak_hours
            ],
            'peak_days': [
                {
                    'day': day_names[day],
                    'probability': round(prob * 100, 1)
                }
                for day, prob in peak_days
            ],
            'model': self.name,
            'description': 'Baseline model using historical hourly and weekday engagement patterns'
        }

if __name__ == "__main__":
    # Example usage
    model = BaselineModel()
    
    # Mock histogram (normally from feature store)
    hour_hist = {
        9: 0.15, 10: 0.12, 11: 0.08, 12: 0.07, 13: 0.06,
        14: 0.05, 15: 0.04, 16: 0.05, 17: 0.08, 18: 0.10,
        19: 0.08, 20: 0.06, 21: 0.04, 22: 0.02
    }
    hour_hist.update({h: 0.0001 for h in range(24) if h not in hour_hist})
    
    weekday_hist = {0: 0.16, 1: 0.15, 2: 0.15, 3: 0.14, 4: 0.13, 5: 0.08, 6: 0.06}
    
    send_time = datetime.now()
    curve = model.predict_engagement_curve(hour_hist, weekday_hist, send_time, hours_ahead=48)
    
    windows = model.find_optimal_send_window(curve, window_size_hours=2, top_k=3)
    
    print("Top 3 Send Windows:")
    for start, end, prob in windows:
        print(f"  {start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%H:%M')}: {prob:.4f}")
    
    explanation = model.explain_prediction(hour_hist, weekday_hist)
    print("\nExplanation:", json.dumps(explanation, indent=2))
