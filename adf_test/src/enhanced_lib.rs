use wasm_bindgen::prelude::*;
use js_sys;
use nalgebra::{DMatrix, DVector};

// Include the same lookup table from the original lib.rs
// (This would be the 50,000+ entry lookup table for p-values)
const ADF_P_VALUE_LOOKUP: &[[f64; 2]] = &[
    // You would copy the entire lookup table from the original lib.rs here
    // For brevity, I'm showing just a few entries as an example
    [-4.98402287309096,0.00002],
    [-4.95836394213414,0.00004],
    // ... (all 50,000+ entries)
    [2.34198462884487,1.0000]
];

#[wasm_bindgen]
pub struct CompleteAdfResult {
    pub test_statistic: f64,
    pub optimal_lags: u32,
    pub aic_value: f64,
    pub p_value: f64,
    critical_values: JsValue,
    pub is_stationary: bool,
}

#[wasm_bindgen]
impl CompleteAdfResult {
    #[wasm_bindgen(getter)]
    pub fn critical_values(&self) -> JsValue {
        self.critical_values.clone()
    }
}

#[wasm_bindgen]
pub struct AdfResult {
    pub statistic: f64,
    pub p_value: f64,
    critical_values: JsValue,
    pub is_stationary: bool,
}

#[wasm_bindgen]
impl AdfResult {
    #[wasm_bindgen(getter)]
    pub fn critical_values(&self) -> JsValue {
        self.critical_values.clone()
    }
}

/// Complete ADF test with optimal lag selection - this is the NEW enhanced function
#[wasm_bindgen]
pub fn calculate_complete_adf_test(data: Vec<f64>, model_type: &str) -> CompleteAdfResult {
    let n = data.len();
    if n < 5 {
        return create_default_adf_result();
    }

    let (min_lags, max_lags) = determine_lag_range(&data, model_type);
    let mut min_aic = f64::INFINITY;
    let mut optimal_test_statistic = 0.0;
    let mut optimal_lags_used = 0;
    let mut optimal_aic = f64::INFINITY;

    // Optimal lag selection using AIC
    for current_lags in min_lags..=max_lags {
        if let Some(result) = calculate_adf_for_lags(&data, current_lags) {
            let aic = calculate_aic(result.ssr, result.n_obs, result.n_params);
            
            if aic < min_aic {
                min_aic = aic;
                optimal_test_statistic = result.test_statistic;
                optimal_lags_used = current_lags;
                optimal_aic = aic;
            }
        }
    }

    let p_value = interpolate_p_value(optimal_test_statistic);
    let is_stationary = determine_stationarity(optimal_test_statistic, p_value);
    let critical_values = create_critical_values_js();

    CompleteAdfResult {
        test_statistic: optimal_test_statistic,
        optimal_lags: optimal_lags_used,
        aic_value: optimal_aic,
        p_value,
        critical_values,
        is_stationary,
    }
}

/// Original p-value lookup function - KEPT for backward compatibility
#[wasm_bindgen]
pub fn get_adf_p_value_and_stationarity(test_statistic: f64) -> AdfResult {
    let p_value = interpolate_p_value(test_statistic);
    let is_stationary = determine_stationarity(test_statistic, p_value);
    let critical_values = create_critical_values_js();

    AdfResult {
        statistic: test_statistic,
        p_value,
        critical_values,
        is_stationary,
    }
}

// Internal structures and helper functions
struct AdfRegressionResult {
    test_statistic: f64,
    ssr: f64,
    n_obs: usize,
    n_params: usize,
}

fn determine_lag_range(data: &[f64], model_type: &str) -> (u32, u32) {
    let n = data.len();
    
    match model_type {
        "ols" => {
            let min_lags = 0;
            let max_lags = (12_u32).min(((n.saturating_sub(3)) / 2) as u32);
            (min_lags, max_lags.max(min_lags))
        },
        _ => (0, 1), // For other models, use minimal lag selection
    }
}

fn calculate_adf_for_lags(data: &[f64], lags: u32) -> Option<AdfRegressionResult> {
    let n = data.len();
    
    // Calculate first differences
    let diff_data: Vec<f64> = data.windows(2).map(|w| w[1] - w[0]).collect();
    
    let effective_start_index = lags as usize;
    if diff_data.len() <= effective_start_index {
        return None;
    }

    // Prepare dependent variable Y (delta_y)
    let y_data: Vec<f64> = diff_data.iter()
        .skip(effective_start_index)
        .copied()
        .collect();
    
    if y_data.is_empty() {
        return None;
    }

    // Prepare independent variables X matrix
    let n_obs = y_data.len();
    let n_params = 2 + lags as usize; // constant + y_{t-1} + lag terms
    
    if n_obs < n_params {
        return None;
    }

    let mut x_matrix = DMatrix::zeros(n_obs, n_params);
    
    for (i, &_y_val) in y_data.iter().enumerate() {
        let data_index = effective_start_index + i;
        
        // Constant term
        x_matrix[(i, 0)] = 1.0;
        
        // y_{t-1} term (lagged level)
        x_matrix[(i, 1)] = data[data_index];
        
        // Lagged difference terms
        for j in 1..=lags as usize {
            if data_index >= j {
                x_matrix[(i, 1 + j)] = diff_data[data_index - j];
            }
        }
    }

    let y_vector = DVector::from_vec(y_data);
    
    // Perform OLS regression using nalgebra (more robust than JS implementation)
    match perform_ols_regression(&x_matrix, &y_vector) {
        Ok((coefficients, ssr)) => {
            // Calculate standard errors for t-statistic
            let mse = ssr / (n_obs - n_params) as f64;
            
            // Calculate (X'X)^-1 for standard errors
            let xtx = x_matrix.transpose() * &x_matrix;
            if let Some(xtx_inv) = xtx.try_inverse() {
                let var_coeff_1 = mse * xtx_inv[(1, 1)]; // Variance of coefficient for y_{t-1}
                let std_err_1 = var_coeff_1.sqrt();
                
                if std_err_1 > 1e-12 && std_err_1.is_finite() {
                    let test_statistic = coefficients[1] / std_err_1;
                    
                    Some(AdfRegressionResult {
                        test_statistic,
                        ssr,
                        n_obs,
                        n_params,
                    })
                } else {
                    None
                }
            } else {
                None
            }
        },
        Err(_) => None,
    }
}

fn perform_ols_regression(x: &DMatrix<f64>, y: &DVector<f64>) -> Result<(DVector<f64>, f64), &'static str> {
    let xt = x.transpose();
    let xtx = &xt * x;
    let xty = &xt * y;
    
    // Solve for coefficients: (X'X)^-1 * X'Y
    // nalgebra provides more robust matrix inversion than the JS implementation
    if let Some(xtx_inv) = xtx.try_inverse() {
        let coefficients = xtx_inv * xty;
        
        // Calculate residual sum of squares
        let y_pred = x * &coefficients;
        let residuals = y - y_pred;
        let ssr = residuals.dot(&residuals);
        
        Ok((coefficients, ssr))
    } else {
        Err("Matrix inversion failed")
    }
}

fn calculate_aic(ssr: f64, n_obs: usize, n_params: usize) -> f64 {
    let n = n_obs as f64;
    let k = n_params as f64;
    n * (ssr / n).ln() + 2.0 * k
}

fn determine_stationarity(test_statistic: f64, p_value: f64) -> bool {
    let critical_5_percent = -2.86;
    p_value <= 0.05 && test_statistic < critical_5_percent
}

fn create_critical_values_js() -> JsValue {
    let critical_values_js = js_sys::Object::new();
    js_sys::Reflect::set(&critical_values_js, &JsValue::from_str("1%"), &JsValue::from_f64(-3.43)).unwrap();
    js_sys::Reflect::set(&critical_values_js, &JsValue::from_str("5%"), &JsValue::from_f64(-2.86)).unwrap();
    js_sys::Reflect::set(&critical_values_js, &JsValue::from_str("10%"), &JsValue::from_f64(-2.57)).unwrap();
    critical_values_js.into()
}

fn create_default_adf_result() -> CompleteAdfResult {
    CompleteAdfResult {
        test_statistic: 0.0,
        optimal_lags: 0,
        aic_value: f64::INFINITY,
        p_value: 1.0,
        critical_values: create_critical_values_js(),
        is_stationary: false,
    }
}

// Linear interpolation function - same as original
fn interpolate_p_value(test_statistic: f64) -> f64 {
    if test_statistic <= ADF_P_VALUE_LOOKUP[0][0] {
        return ADF_P_VALUE_LOOKUP[0][1];
    }
    if test_statistic >= ADF_P_VALUE_LOOKUP[ADF_P_VALUE_LOOKUP.len() - 1][0] {
        return ADF_P_VALUE_LOOKUP[ADF_P_VALUE_LOOKUP.len() - 1][1];
    }

    let mut low = 0;
    let mut high = ADF_P_VALUE_LOOKUP.len() - 1;
    let mut idx = 0;

    // Find the interval using binary search
    while low <= high {
        let mid = low + (high - low) / 2;
        if ADF_P_VALUE_LOOKUP[mid][0] == test_statistic {
            return ADF_P_VALUE_LOOKUP[mid][1];
        } else if ADF_P_VALUE_LOOKUP[mid][0] < test_statistic {
            idx = mid;
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }

    let x1 = ADF_P_VALUE_LOOKUP[idx][0];
    let y1 = ADF_P_VALUE_LOOKUP[idx][1];
    let x2 = ADF_P_VALUE_LOOKUP[idx + 1][0];
    let y2 = ADF_P_VALUE_LOOKUP[idx + 1][1];

    // Linear interpolation formula
    y1 + (test_statistic - x1) * (y2 - y1) / (x2 - x1)
}