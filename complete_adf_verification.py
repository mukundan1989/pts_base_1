#!/usr/bin/env python3
"""
Complete ADF Test Verification for TCS-HCL Stock Data
Processes full dataset and compares with Enhanced WASM results

Usage:
1. Save your TCS-HCL data as 'tcs_hcl_data.csv' 
2. Run: python3 complete_adf_verification.py
3. Compare results with your WASM output
"""

import csv
import math

def load_stock_data(filename='tcs_hcl_data.csv'):
    """Load TCS-HCL stock data from CSV file"""
    data = []
    try:
        with open(filename, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                data.append({
                    'date': row['DATE'],
                    'tcs': float(row['TCS']),
                    'hcl': float(row['HCL'])
                })
        
        # Sort by date (chronological order)
        data.sort(key=lambda x: x['date'])
        return data
        
    except FileNotFoundError:
        print(f"❌ File '{filename}' not found!")
        print("📝 Please create a CSV file with columns: DATE,TCS,HCL")
        return None
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None

def rolling_ols_regression(tcs_values, hcl_values, window_size=60):
    """Calculate rolling OLS regression coefficients"""
    if len(tcs_values) < window_size:
        return None, None
        
    # Use last window_size observations
    tcs_window = tcs_values[-window_size:]
    hcl_window = hcl_values[-window_size:]
    
    n = len(tcs_window)
    
    # Calculate means
    tcs_mean = sum(tcs_window) / n
    hcl_mean = sum(hcl_window) / n
    
    # Calculate OLS coefficients: HCL = alpha + beta * TCS + epsilon
    numerator = sum((tcs_window[i] - tcs_mean) * (hcl_window[i] - hcl_mean) for i in range(n))
    denominator = sum((tcs_window[i] - tcs_mean) ** 2 for i in range(n))
    
    if denominator == 0:
        return None, None
        
    beta = numerator / denominator  # Hedge ratio
    alpha = hcl_mean - beta * tcs_mean  # Intercept
    
    return alpha, beta

def calculate_spread_series(data, lookback_window=60):
    """Calculate complete spread series using rolling OLS"""
    print(f"📊 Calculating spread series with {lookback_window}-day rolling window...")
    
    spreads = []
    regression_stats = []
    
    for i in range(lookback_window, len(data)):
        # Get price arrays up to current point
        tcs_prices = [data[j]['tcs'] for j in range(i + 1)]
        hcl_prices = [data[j]['hcl'] for j in range(i + 1)]
        
        # Calculate rolling regression
        alpha, beta = rolling_ols_regression(tcs_prices, hcl_prices, lookback_window)
        
        if alpha is not None and beta is not None:
            # Current prices
            current_tcs = data[i]['tcs']
            current_hcl = data[i]['hcl']
            
            # Calculate spread: HCL - (alpha + beta * TCS)
            spread = current_hcl - (alpha + beta * current_tcs)
            spreads.append(spread)
            
            regression_stats.append({
                'date': data[i]['date'],
                'alpha': alpha,
                'beta': beta,
                'spread': spread,
                'tcs': current_tcs,
                'hcl': current_hcl
            })
    
    return spreads, regression_stats

def augmented_dickey_fuller_test(data, max_lags=12):
    """
    Enhanced ADF test implementation
    Tests: Δy_t = α + βy_{t-1} + Σ(γ_i * Δy_{t-i}) + ε_t
    """
    if len(data) < max_lags + 10:
        return None
    
    best_result = None
    best_aic = float('inf')
    
    print(f"🔬 Testing ADF with lags 1 to {max_lags}...")
    
    for lags in range(1, min(max_lags + 1, len(data) // 4)):
        try:
            result = adf_test_with_lags(data, lags)
            if result and result['aic'] < best_aic:
                best_aic = result['aic']
                best_result = result
                best_result['optimal_lags'] = lags
        except Exception as e:
            continue
    
    return best_result

def adf_test_with_lags(data, lags):
    """ADF test with specified number of lags"""
    n = len(data)
    
    if n < lags + 10:
        return None
    
    # Prepare regression data
    # Δy_t = α + βy_{t-1} + Σ(γ_i * Δy_{t-i}) + ε_t
    
    # Calculate first differences
    diff_y = [data[i] - data[i-1] for i in range(1, n)]
    
    # Prepare regression matrices
    y_regression = diff_y[lags:]  # Dependent variable
    x_regression = []  # Independent variables
    
    for i in range(lags, len(diff_y)):
        row = [1.0]  # Constant term
        row.append(data[i])  # y_{t-1} level term
        
        # Add lagged differences
        for lag in range(1, lags + 1):
            if i - lag >= 0:
                row.append(diff_y[i - lag])
            else:
                row.append(0.0)
        
        x_regression.append(row)
    
    if len(y_regression) != len(x_regression) or len(x_regression) == 0:
        return None
    
    # Solve OLS regression: y = X * beta
    try:
        coefficients = solve_ols(x_regression, y_regression)
        if coefficients is None:
            return None
        
        # Extract beta coefficient (coefficient of y_{t-1})
        beta_coef = coefficients[1]
        
        # Calculate residuals and statistics
        residuals = []
        for i in range(len(y_regression)):
            predicted = sum(x_regression[i][j] * coefficients[j] for j in range(len(coefficients)))
            residual = y_regression[i] - predicted
            residuals.append(residual)
        
        # Calculate standard error and t-statistic
        n_obs = len(residuals)
        k_params = len(coefficients)
        
        if n_obs <= k_params:
            return None
        
        rss = sum(r ** 2 for r in residuals)  # Residual sum of squares
        mse = rss / (n_obs - k_params)
        
        # Calculate standard error of beta coefficient
        x_matrix_for_beta = [row[1] for row in x_regression]  # y_{t-1} column
        x_mean = sum(x_matrix_for_beta) / len(x_matrix_for_beta)
        x_var = sum((x - x_mean) ** 2 for x in x_matrix_for_beta)
        
        if x_var == 0:
            return None
        
        se_beta = math.sqrt(mse / x_var)
        
        if se_beta == 0:
            return None
        
        t_statistic = beta_coef / se_beta
        
        # Calculate AIC
        log_likelihood = -0.5 * n_obs * (math.log(2 * math.pi) + math.log(mse) + 1)
        aic = 2 * k_params - 2 * log_likelihood
        
        return {
            'test_statistic': t_statistic,
            'beta_coefficient': beta_coef,
            'standard_error': se_beta,
            'aic': aic,
            'n_observations': n_obs,
            'residual_sum_squares': rss
        }
        
    except Exception as e:
        return None

def solve_ols(X, y):
    """Solve OLS regression using normal equations: β = (X'X)^(-1)X'y"""
    try:
        n_rows = len(X)
        n_cols = len(X[0]) if n_rows > 0 else 0
        
        if n_rows == 0 or n_cols == 0:
            return None
        
        # Calculate X'X
        XtX = [[0.0] * n_cols for _ in range(n_cols)]
        for i in range(n_cols):
            for j in range(n_cols):
                for k in range(n_rows):
                    XtX[i][j] += X[k][i] * X[k][j]
        
        # Calculate X'y
        Xty = [0.0] * n_cols
        for i in range(n_cols):
            for k in range(n_rows):
                Xty[i] += X[k][i] * y[k]
        
        # Solve (X'X)β = X'y using Gaussian elimination
        coefficients = gaussian_elimination(XtX, Xty)
        return coefficients
        
    except Exception as e:
        return None

def gaussian_elimination(A, b):
    """Solve Ax = b using Gaussian elimination"""
    try:
        n = len(A)
        
        # Forward elimination
        for i in range(n):
            # Find pivot
            max_row = i
            for k in range(i + 1, n):
                if abs(A[k][i]) > abs(A[max_row][i]):
                    max_row = k
            
            # Swap rows
            A[i], A[max_row] = A[max_row], A[i]
            b[i], b[max_row] = b[max_row], b[i]
            
            # Check for singular matrix
            if abs(A[i][i]) < 1e-10:
                return None
            
            # Eliminate column
            for k in range(i + 1, n):
                if A[i][i] != 0:
                    factor = A[k][i] / A[i][i]
                    for j in range(i, n):
                        A[k][j] -= factor * A[i][j]
                    b[k] -= factor * b[i]
        
        # Back substitution
        x = [0.0] * n
        for i in range(n - 1, -1, -1):
            x[i] = b[i]
            for j in range(i + 1, n):
                x[i] -= A[i][j] * x[j]
            if A[i][i] != 0:
                x[i] /= A[i][i]
            else:
                return None
        
        return x
        
    except Exception as e:
        return None

def analyze_complete_dataset():
    """Main analysis function for complete TCS-HCL dataset"""
    print("🔍 Complete TCS-HCL ADF Test Verification")
    print("=" * 50)
    
    # Load data
    data = load_stock_data()
    if not data:
        print("\n📝 To run this analysis:")
        print("1. Create 'tcs_hcl_data.csv' with your complete dataset")
        print("2. Format: DATE,TCS,HCL (headers required)")
        print("3. Run this script again")
        return
    
    print(f"✅ Loaded {len(data)} observations")
    print(f"📅 Date range: {data[0]['date']} to {data[-1]['date']}")
    
    # Calculate spread series
    spreads, regression_stats = calculate_spread_series(data, 60)
    
    if len(spreads) < 50:
        print(f"❌ Insufficient spread data: {len(spreads)} observations")
        return
    
    print(f"✅ Generated {len(spreads)} spread observations")
    
    # Spread statistics
    spread_mean = sum(spreads) / len(spreads)
    spread_var = sum((s - spread_mean) ** 2 for s in spreads) / len(spreads)
    spread_std = math.sqrt(spread_var)
    
    print(f"\n📊 Spread Statistics:")
    print(f"   Mean: {spread_mean:.6f}")
    print(f"   Std Dev: {spread_std:.6f}")
    print(f"   Min: {min(spreads):.6f}")
    print(f"   Max: {max(spreads):.6f}")
    
    # Recent regression stats
    if regression_stats:
        recent = regression_stats[-1]
        print(f"\n📈 Latest OLS Regression ({recent['date']}):")
        print(f"   Alpha (Intercept): {recent['alpha']:.6f}")
        print(f"   Beta (Hedge Ratio): {recent['beta']:.6f}")
        print(f"   Current Spread: {recent['spread']:.6f}")
    
    # Perform ADF test
    print(f"\n🧪 Enhanced ADF Test Analysis:")
    print("-" * 30)
    
    adf_result = augmented_dickey_fuller_test(spreads)
    
    if adf_result:
        print(f"✅ ADF Test Results:")
        print(f"   Test Statistic: {adf_result['test_statistic']:.8f}")
        print(f"   Optimal Lags: {adf_result['optimal_lags']}")
        print(f"   AIC Value: {adf_result['aic']:.3f}")
        print(f"   Beta Coefficient: {adf_result['beta_coefficient']:.8f}")
        print(f"   Standard Error: {adf_result['standard_error']:.8f}")
        print(f"   Observations Used: {adf_result['n_observations']}")
        
        # Stationarity assessment
        is_stationary = adf_result['test_statistic'] < -2.86  # Rough 5% critical value
        print(f"   Stationarity: {'✅ Likely Stationary' if is_stationary else '❌ Likely Non-Stationary'}")
        
        print(f"\n🎯 Comparison with Enhanced WASM:")
        print(f"   Your WASM t-stat: -6.21653412")
        print(f"   This calculation: {adf_result['test_statistic']:.8f}")
        
        diff = abs(-6.21653412 - adf_result['test_statistic'])
        print(f"   Absolute difference: {diff:.8f}")
        
        if diff < 0.5:
            print(f"   ✅ EXCELLENT MATCH! (< 0.5 difference)")
        elif diff < 1.0:
            print(f"   ✅ GOOD MATCH! (< 1.0 difference)")
        elif diff < 2.0:
            print(f"   ⚠️  Reasonable difference (< 2.0)")
        else:
            print(f"   ⚠️  Significant difference (> 2.0)")
        
        print(f"\n   WASM optimal lags: 12")
        print(f"   This calculation: {adf_result['optimal_lags']}")
        
        print(f"\n   WASM AIC: 7247.428")
        print(f"   This calculation: {adf_result['aic']:.3f}")
        
    else:
        print("❌ ADF test failed - insufficient data or numerical issues")
    
    print(f"\n💡 Analysis Summary:")
    print(f"   • Dataset: {len(data)} total observations")
    print(f"   • Spreads: {len(spreads)} spread calculations")
    print(f"   • Method: 60-day rolling OLS regression")
    print(f"   • Model: HCL = α + β×TCS + ε")

if __name__ == "__main__":
    analyze_complete_dataset()