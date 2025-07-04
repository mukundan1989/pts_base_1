import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import adfuller
from sklearn.linear_model import LinearRegression
from io import StringIO
import warnings
warnings.filterwarnings('ignore')

# Stock data from user (TCS, HCL prices)
data_csv = """DATE,TCS,HCL
2025-01-17,4124.299805,1788.9
2025-01-16,4196.299805,1780.25
2025-01-15,4239.49707,1813.476
2025-01-14,4222.986328,1801.407
2025-01-13,4280.898438,1976.08
2025-01-10,4255.508789,1981.742
2025-01-09,4029.248291,1921.846
2025-01-08,4098.632813,1919.313
2025-01-07,4018.723145,1903.072
2025-01-06,4085.264648,1939.973
2025-01-03,4090.152832,1933.616
2025-01-02,4165.822754,1958.995
2025-01-01,4102.67334,1899.148
2024-12-31,4085.065186,1904.562
2024-12-30,4148.912598,1916.035
2024-12-27,4154.94873,1879.332
2024-12-26,4159.188477,1888.024
2024-12-24,4169.563477,1884.249
2024-12-23,4148.414063,1890.258
2024-12-20,4160.385254,1898.552"""

def load_and_prepare_data():
    """Load stock data and prepare for analysis"""
    # Note: This is abbreviated data - full data would be loaded from user's complete dataset
    df = pd.read_csv(StringIO(data_csv))
    df['DATE'] = pd.to_datetime(df['DATE'])
    df = df.sort_values('DATE').reset_index(drop=True)  # Sort chronologically
    return df

def calculate_ols_spread(tcs_prices, hcl_prices, lookback_window=60):
    """Calculate OLS regression spread for pairs trading"""
    if len(tcs_prices) < lookback_window:
        return None, None, None
        
    # Use lookback window for regression
    tcs_window = tcs_prices[-lookback_window:].values.reshape(-1, 1)
    hcl_window = hcl_prices[-lookback_window:].values
    
    # Fit OLS regression: HCL = alpha + beta * TCS + epsilon
    model = LinearRegression()
    model.fit(tcs_window, hcl_window)
    
    beta = model.coef_[0]
    alpha = model.intercept_
    
    # Calculate current spread: HCL - (alpha + beta * TCS)
    current_spread = hcl_prices.iloc[-1] - (alpha + beta * tcs_prices.iloc[-1])
    
    return current_spread, beta, alpha

def enhanced_adf_test(data, model_type='ols', max_lags=12):
    """
    Enhanced ADF test matching the WASM implementation
    """
    if len(data) < 10:
        return None
        
    # Clean data - remove NaN and infinite values
    clean_data = data.dropna()
    clean_data = clean_data[np.isfinite(clean_data)]
    
    if len(clean_data) < 10:
        return None
    
    # Perform ADF test with automatic lag selection
    try:
        # Use AIC for optimal lag selection (up to max_lags)
        optimal_lags = min(max_lags, len(clean_data) // 4)
        
        best_aic = float('inf')
        best_result = None
        best_lags = 1
        
        for lags in range(1, optimal_lags + 1):
            try:
                result = adfuller(clean_data, maxlag=lags, regression='c', autolag=None)
                
                # Calculate AIC manually for this lag
                n = len(clean_data) - lags
                residual_ss = result[4]['nobs'] * np.log(2 * np.pi) + result[4]['nobs'] * np.log(result[4]['resvar']) + result[4]['nobs']
                aic = 2 * (lags + 1) + residual_ss
                
                if aic < best_aic:
                    best_aic = aic
                    best_result = result
                    best_lags = lags
                    
            except Exception as e:
                continue
        
        if best_result is None:
            return None
            
        return {
            'test_statistic': best_result[0],
            'p_value': best_result[1],
            'optimal_lags': best_lags,
            'aic_value': best_aic,
            'critical_values': best_result[4]['1%'], 
            'is_stationary': best_result[1] < 0.05,
            'n_observations': len(clean_data)
        }
        
    except Exception as e:
        print(f"ADF test failed: {e}")
        return None

def analyze_tcs_hcl_pair():
    """Main analysis function"""
    print("🔍 TCS-HCL Pairs Trading ADF Analysis")
    print("=" * 50)
    
    # Note: This uses abbreviated data for demonstration
    # In practice, you would load the full dataset provided by the user
    df = load_and_prepare_data()
    print(f"📊 Data loaded: {len(df)} observations")
    print(f"📅 Date range: {df['DATE'].min()} to {df['DATE'].max()}")
    
    # Calculate 60-day rolling OLS spread (using available data)
    lookback = min(60, len(df) - 1)
    spread, beta, alpha = calculate_ols_spread(df['TCS'], df['HCL'], lookback)
    
    if spread is None:
        print("❌ Insufficient data for OLS regression")
        return
        
    print(f"\n📈 OLS Regression Results (last {lookback} days):")
    print(f"   Beta (hedge ratio): {beta:.6f}")
    print(f"   Alpha (intercept): {alpha:.6f}")
    print(f"   Current spread: {spread:.6f}")
    
    # Create spread series for ADF test
    spreads = []
    for i in range(lookback, len(df)):
        window_spread, _, _ = calculate_ols_spread(
            df['TCS'].iloc[:i+1], 
            df['HCL'].iloc[:i+1], 
            lookback
        )
        if window_spread is not None:
            spreads.append(window_spread)
    
    if len(spreads) < 10:
        print("❌ Insufficient spread data for ADF test")
        return
        
    spreads_series = pd.Series(spreads)
    print(f"\n📊 Spread series: {len(spreads_series)} observations")
    print(f"   Mean: {spreads_series.mean():.6f}")
    print(f"   Std: {spreads_series.std():.6f}")
    
    # Perform enhanced ADF test
    print(f"\n🧪 Enhanced ADF Test Results:")
    print("-" * 30)
    
    adf_result = enhanced_adf_test(spreads_series, 'ols')
    
    if adf_result:
        print(f"   Test Statistic: {adf_result['test_statistic']:.8f}")
        print(f"   Optimal Lags: {adf_result['optimal_lags']}")
        print(f"   AIC Value: {adf_result['aic_value']:.3f}")
        print(f"   P-value: {adf_result['p_value']:.6f}")
        print(f"   Is Stationary: {adf_result['is_stationary']}")
        print(f"   Critical Value (1%): {adf_result['critical_values']:.6f}")
        print(f"   Observations Used: {adf_result['n_observations']}")
        
        print(f"\n🎯 Comparison with Enhanced WASM:")
        print(f"   User's WASM t-stat: -6.21653412")
        print(f"   This analysis t-stat: {adf_result['test_statistic']:.8f}")
        print(f"   Difference: {abs(-6.21653412 - adf_result['test_statistic']):.8f}")
        
    else:
        print("   ❌ ADF test failed")

if __name__ == "__main__":
    analyze_tcs_hcl_pair()
    
    print(f"\n💡 Note: This analysis uses abbreviated data.")
    print(f"   To verify with your complete dataset:")
    print(f"   1. Replace data_csv with your full TCS-HCL dataset")
    print(f"   2. Ensure 60-day rolling window calculations")
    print(f"   3. Compare with your WASM results: t-stat=-6.21653412")