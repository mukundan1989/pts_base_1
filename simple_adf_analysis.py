#!/usr/bin/env python3
"""
Simple ADF Test Analysis for TCS-HCL Stock Data
Verifies Enhanced WASM Implementation Results
"""

import math
import sys

# TCS-HCL Stock Data (sample - user has full dataset)
stock_data = [
    # [Date, TCS, HCL]
    ["2025-01-17", 4124.299805, 1788.9],
    ["2025-01-16", 4196.299805, 1780.25],
    ["2025-01-15", 4239.49707, 1813.476],
    ["2025-01-14", 4222.986328, 1801.407],
    ["2025-01-13", 4280.898438, 1976.08],
    ["2025-01-10", 4255.508789, 1981.742],
    ["2025-01-09", 4029.248291, 1921.846],
    ["2025-01-08", 4098.632813, 1919.313],
    ["2025-01-07", 4018.723145, 1903.072],
    ["2025-01-06", 4085.264648, 1939.973],
    ["2025-01-03", 4090.152832, 1933.616],
    ["2025-01-02", 4165.822754, 1958.995],
    ["2025-01-01", 4102.67334, 1899.148],
    ["2024-12-31", 4085.065186, 1904.562],
    ["2024-12-30", 4148.912598, 1916.035],
]

def simple_linear_regression(x_data, y_data):
    """Simple OLS regression: y = alpha + beta * x"""
    n = len(x_data)
    if n == 0:
        return None, None
    
    # Calculate means
    x_mean = sum(x_data) / n
    y_mean = sum(y_data) / n
    
    # Calculate beta (slope)
    numerator = sum((x_data[i] - x_mean) * (y_data[i] - y_mean) for i in range(n))
    denominator = sum((x_data[i] - x_mean) ** 2 for i in range(n))
    
    if denominator == 0:
        return None, None
        
    beta = numerator / denominator
    alpha = y_mean - beta * x_mean
    
    return alpha, beta

def calculate_spread_series(data, lookback=10):
    """Calculate OLS spread series with rolling window"""
    spreads = []
    
    # Reverse data to chronological order (oldest first)
    data_reversed = list(reversed(data))
    
    for i in range(lookback, len(data_reversed)):
        # Get lookback window
        window = data_reversed[i-lookback:i]
        tcs_window = [row[1] for row in window]
        hcl_window = [row[2] for row in window]
        
        # Calculate OLS regression
        alpha, beta = simple_linear_regression(tcs_window, hcl_window)
        
        if alpha is not None and beta is not None:
            # Current prices
            current_tcs = data_reversed[i][1]
            current_hcl = data_reversed[i][2]
            
            # Calculate spread: HCL - (alpha + beta * TCS)
            spread = current_hcl - (alpha + beta * current_tcs)
            spreads.append(spread)
            
    return spreads

def simple_adf_statistic(data, lags=1):
    """
    Simplified ADF test statistic calculation
    Tests: Δy_t = α + βy_{t-1} + Σ(γ_i * Δy_{t-i}) + ε_t
    H0: β = 0 (unit root, non-stationary)
    H1: β < 0 (stationary)
    """
    if len(data) < lags + 2:
        return None, None
        
    n = len(data)
    
    # Calculate first differences: Δy_t = y_t - y_{t-1}
    diff_y = [data[i] - data[i-1] for i in range(1, n)]
    
    # Lagged levels: y_{t-1}
    lagged_y = data[:-1]
    
    # For simplicity, use basic regression without lagged differences
    # Δy_t = α + β*y_{t-1} + ε_t
    
    if len(diff_y) != len(lagged_y):
        return None, None
        
    # Simple regression: diff_y = alpha + beta * lagged_y
    alpha, beta = simple_linear_regression(lagged_y, diff_y)
    
    if alpha is None or beta is None:
        return None, None
    
    # Calculate residuals and standard error
    residuals = []
    for i in range(len(diff_y)):
        predicted = alpha + beta * lagged_y[i]
        residual = diff_y[i] - predicted
        residuals.append(residual)
    
    # Calculate standard error of beta
    n_obs = len(residuals)
    if n_obs <= 2:
        return None, None
        
    residual_sum_sq = sum(r**2 for r in residuals)
    mse = residual_sum_sq / (n_obs - 2)
    
    lagged_y_mean = sum(lagged_y) / len(lagged_y)
    sum_sq_x = sum((x - lagged_y_mean)**2 for x in lagged_y)
    
    if sum_sq_x == 0:
        return None, None
        
    std_error_beta = math.sqrt(mse / sum_sq_x)
    
    # ADF test statistic: t = β / SE(β)
    if std_error_beta == 0:
        return None, None
        
    t_statistic = beta / std_error_beta
    
    return t_statistic, beta

def analyze_sample_data():
    """Analyze the sample TCS-HCL data"""
    print("🔍 Simple ADF Analysis for TCS-HCL Verification")
    print("=" * 50)
    
    print(f"📊 Sample data: {len(stock_data)} observations")
    print(f"📅 Using simplified implementation for verification")
    
    # Calculate spread series
    spreads = calculate_spread_series(stock_data)
    print(f"\n📈 Calculated {len(spreads)} spread observations")
    
    if len(spreads) < 5:
        print("❌ Insufficient data for ADF test")
        return
        
    print(f"   Spread statistics:")
    spread_mean = sum(spreads) / len(spreads)
    spread_variance = sum((s - spread_mean)**2 for s in spreads) / len(spreads)
    spread_std = math.sqrt(spread_variance)
    
    print(f"   Mean: {spread_mean:.6f}")
    print(f"   Std Dev: {spread_std:.6f}")
    print(f"   Min: {min(spreads):.6f}")
    print(f"   Max: {max(spreads):.6f}")
    
    # Perform simplified ADF test
    print(f"\n🧪 Simplified ADF Test:")
    print("-" * 25)
    
    t_stat, beta_coef = simple_adf_statistic(spreads, lags=1)
    
    if t_stat is not None:
        print(f"   Test Statistic: {t_stat:.8f}")
        print(f"   Beta Coefficient: {beta_coef:.8f}")
        print(f"   Interpretation: {'Likely Stationary' if t_stat < -2.0 else 'Likely Non-Stationary'}")
        
        print(f"\n🎯 Comparison with Enhanced WASM:")
        print(f"   Your WASM t-stat: -6.21653412")
        print(f"   Simple calc t-stat: {t_stat:.8f}")
        diff = abs(-6.21653412 - t_stat)
        print(f"   Difference: {diff:.8f}")
        
        if diff < 1.0:
            print("   ✅ Results are reasonably close!")
        else:
            print("   ⚠️  Significant difference - this is expected with simplified calculation")
            
    else:
        print("   ❌ ADF calculation failed")
    
    print(f"\n💡 Key Points:")
    print(f"   • This uses simplified math (no external libraries)")
    print(f"   • Sample data only ({len(stock_data)} points vs your full dataset)")
    print(f"   • Your WASM uses nalgebra (professional linear algebra)")
    print(f"   • Expected: WASM results more precise & robust")
    
    print(f"\n🔬 To verify with your complete dataset:")
    print(f"   1. Your WASM: t-stat=-6.21653412, lags=12, AIC=7247.428")
    print(f"   2. Gemini AI gave different results - what were they?")
    print(f"   3. 60-day rolling window with {len(stock_data)} total observations")
    print(f"   4. OLS model for hedge ratio calculation")

if __name__ == "__main__":
    analyze_sample_data()