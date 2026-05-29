"""Anomaly detection using z-score on numeric columns."""
import numpy as np
from typing import Optional, Dict, Any

def detect_anomalies(result: Dict[str, Any], threshold: float = 2.5) -> Optional[str]:
    if not result or not result.get("rows"):
        return None
    
    rows = result["rows"]
    if len(rows) < 3:
        return None
    
    numeric_cols = []
    for col in result["columns"]:
        try:
            values = [float(r[col]) for r in rows if r.get(col) is not None]
            if len(values) >= 3:
                numeric_cols.append((col, values))
        except (ValueError, TypeError):
            continue
    
    if not numeric_cols:
        return None
    
    for col, values in numeric_cols:
        mean = np.mean(values)
        std = np.std(values)
        if std == 0:
            continue
        
        for i, val in enumerate(values):
            z_score = abs((val - mean) / std)
            if z_score > threshold:
                row = rows[i]
                label_col = next(
                    (c for c in result["columns"] if c != col and isinstance(row.get(c), str)),
                    None
                )
                label = f" ({row[label_col]})" if label_col else ""
                return (
                    f"The ₹{abs(val):,.0f} transaction{label} is {z_score:.1f}x "
                    f"the standard deviation from the mean — likely an outlier."
                )
    
    return None
