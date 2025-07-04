// Enhanced calculations-worker.js
// This replaces your existing public/workers/calculations-worker.js

// Import the ENHANCED WASM module with both functions
import init, { 
  get_adf_p_value_and_stationarity,  // Original function (backward compatibility)
  calculate_complete_adf_test          // NEW enhanced function
} from "../wasm/adf_test.js"

let wasmInitialized = false

// Initialize WASM module once
async function initializeWasm() {
  if (!wasmInitialized) {
    self.postMessage({ type: "debug", message: "Initializing enhanced WASM..." })
    try {
      await init()
      wasmInitialized = true
      self.postMessage({ type: "debug", message: "Enhanced WASM initialized." })
    } catch (e) {
      console.error("Failed to initialize enhanced WASM:", e)
      self.postMessage({
        type: "error",
        message: `Enhanced WASM initialization error: ${e instanceof Error ? e.message : String(e)}`,
      })
      throw e
    }
  }
}

// Call this immediately to start loading WASM in the background
initializeWasm()

// ENHANCED ADF Test function using complete WASM calculation
const adfTestWasm = async (data, seriesType, modelType) => {
  // Filter out NaN and Infinity values
  const cleanData = data.filter((val) => typeof val === "number" && isFinite(val))

  self.postMessage({
    type: "debug",
    message: `Enhanced ADF Test: Received ${data.length} raw data points for ${seriesType}. Cleaned to ${cleanData.length} points.`,
  })

  if (cleanData.length < 5) {
    self.postMessage({
      type: "debug",
      message: `Enhanced ADF Test: Not enough clean data points (${cleanData.length}) for ADF test. Returning default.`,
    })
    return { 
      statistic: 0, 
      pValue: 1, 
      criticalValues: { "1%": 0, "5%": 0, "10%": 0 }, 
      isStationary: false,
      optimalLags: 0,
      aicValue: Infinity,
      method: "insufficient_data"
    }
  }

  try {
    await initializeWasm() // Ensure WASM is loaded

    // NEW: Use complete WASM calculation instead of JavaScript
    const result = calculate_complete_adf_test(cleanData, modelType)

    self.postMessage({ 
      type: "debug", 
      message: `Enhanced ADF Test: Complete WASM result: statistic=${result.test_statistic}, lags=${result.optimal_lags}, AIC=${result.aic_value}` 
    })

    return {
      statistic: result.test_statistic,
      pValue: result.p_value,
      criticalValues: result.critical_values,
      isStationary: result.is_stationary,
      // Enhanced information from WASM
      optimalLags: result.optimal_lags,
      aicValue: result.aic_value,
      method: "complete_wasm_calculation"
    }
  } catch (error) {
    console.error("Error running enhanced ADF test with WASM:", error)
    self.postMessage({ type: "error", message: `Enhanced ADF Test WASM error: ${error.message}` })
    
    // Fallback to default values
    return { 
      statistic: 0, 
      pValue: 1, 
      criticalValues: { "1%": 0, "5%": 0, "10%": 0 }, 
      isStationary: false,
      optimalLags: 0,
      aicValue: Infinity,
      method: "error_fallback"
    }
  }
}

// Keep all your existing utility functions
const calculateZScore = (data, lookback) => {
  // ... your existing implementation
}

const multiplyMatrices = (A, B) => {
  // ... your existing implementation  
}

// ... all other existing functions ...

// Main message handler for the worker (UPDATED)
self.onmessage = async (event) => {
  const {
    type,
    data: { pricesA, pricesB },
    params,
    selectedPair,
  } = event.data

  if (type === "runAnalysis") {
    // Ensure WASM is ready before proceeding with analysis
    await initializeWasm()

    const {
      modelType,
      ratioLookbackWindow,
      olsLookbackWindow,
      kalmanProcessNoise,
      kalmanMeasurementNoise,
      kalmanInitialLookback,
      euclideanLookbackWindow,
      zScoreLookback,
      entryThreshold,
      exitThreshold,
    } = params

    let analysisData = null
    let error = ""

    try {
      // ... your existing analysis logic ...
      const minLength = Math.min(pricesA.length, pricesB.length)
      const dates = pricesA.map((d) => d.date).slice(0, minLength)
      const stockAPrices = pricesA.map((d) => d.close).slice(0, minLength)
      const stockBPrices = pricesB.map((d) => d.close).slice(0, minLength)

      // ... existing spread/ratio/distance calculations ...

      // UPDATED: Use ENHANCED WASM for ADF test
      const seriesForADF = modelType === "ratio" ? ratios : modelType === "euclidean" ? distances : spreads
      const seriesTypeForADF = modelType === "ratio" ? "ratios" : modelType === "euclidean" ? "distances" : "spreads"
      
      // This now uses complete WASM calculation instead of JavaScript + WASM lookup
      const adfResults = await adfTestWasm(seriesForADF, seriesTypeForADF, modelType)

      // ... rest of your existing analysis logic ...

      analysisData = {
        dates,
        ratios,
        spreads,
        distances,
        hedgeRatios,
        alphas,
        zScores,
        stockAPrices,
        stockBPrices,
        statistics: {
          correlation,
          // ... existing statistics ...
          adfResults, // Now includes enhanced information
          // ... rest of statistics ...
        },
        tableData,
        chartData: {
          rollingMean,
          rollingUpperBand1,
          rollingLowerBand1,
          rollingUpperBand2,
          rollingLowerBand2,
        },
      }
    } catch (e) {
      console.error("Error in enhanced calculations worker:", e)
      error = e.message || "An unknown error occurred during enhanced analysis."
    } finally {
      self.postMessage({ type: "analysisComplete", analysisData, error })
    }
  }
}