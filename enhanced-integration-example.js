// Enhanced WASM Integration Example
// This shows how to use both the original p-value lookup AND the new complete ADF test

import init, { 
  get_adf_p_value_and_stationarity,  // Original function (p-value lookup only)
  calculate_complete_adf_test          // NEW function (complete ADF calculation)
} from "../wasm/adf_test.js"

let wasmInitialized = false

async function initializeWasm() {
  if (!wasmInitialized) {
    try {
      await init()
      wasmInitialized = true
      console.log("Enhanced WASM initialized successfully")
    } catch (e) {
      console.error("Failed to initialize enhanced WASM:", e)
      throw e
    }
  }
}

// OLD approach: JavaScript calculates test statistic, WASM does p-value lookup
const adfTestOldWay = async (data, seriesType, modelType) => {
  await initializeWasm()
  
  // Clean data
  const cleanData = data.filter((val) => typeof val === "number" && isFinite(val))
  
  if (cleanData.length < 5) {
    return { statistic: 0, pValue: 1, criticalValues: { "1%": 0, "5%": 0, "10%": 0 }, isStationary: false }
  }

  try {
    // JavaScript calculates test statistic (with potential precision issues)
    const testStatistic = calculateAdfTestStatistic(cleanData, modelType) // Your existing JS function
    
    // WASM only does p-value lookup
    const result = get_adf_p_value_and_stationarity(testStatistic)

    return {
      statistic: result.statistic,
      pValue: result.p_value,
      criticalValues: result.critical_values,
      isStationary: result.is_stationary,
      // Additional info
      method: "javascript_calculation_wasm_lookup"
    }
  } catch (error) {
    console.error("Error in old ADF test:", error)
    return { statistic: 0, pValue: 1, criticalValues: { "1%": 0, "5%": 0, "10%": 0 }, isStationary: false }
  }
}

// NEW approach: WASM calculates EVERYTHING (test statistic + p-value)
const adfTestNewWay = async (data, seriesType, modelType) => {
  await initializeWasm()
  
  // Clean data
  const cleanData = data.filter((val) => typeof val === "number" && isFinite(val))
  
  if (cleanData.length < 5) {
    return { 
      statistic: 0, 
      pValue: 1, 
      criticalValues: { "1%": 0, "5%": 0, "10%": 0 }, 
      isStationary: false,
      optimalLags: 0,
      aicValue: Infinity
    }
  }

  try {
    // WASM calculates EVERYTHING with better precision
    const result = calculate_complete_adf_test(cleanData, modelType)

    return {
      statistic: result.test_statistic,
      pValue: result.p_value,
      criticalValues: result.critical_values,
      isStationary: result.is_stationary,
      // Additional information from enhanced WASM
      optimalLags: result.optimal_lags,
      aicValue: result.aic_value,
      method: "complete_wasm_calculation"
    }
  } catch (error) {
    console.error("Error in enhanced ADF test:", error)
    return { 
      statistic: 0, 
      pValue: 1, 
      criticalValues: { "1%": 0, "5%": 0, "10%": 0 }, 
      isStationary: false,
      optimalLags: 0,
      aicValue: Infinity
    }
  }
}

// Comparison function to see differences between methods
const compareAdfMethods = async (data, seriesType, modelType) => {
  console.log(`\n=== ADF Test Comparison for ${seriesType} (${modelType}) ===`)
  
  const oldResult = await adfTestOldWay(data, seriesType, modelType)
  const newResult = await adfTestNewWay(data, seriesType, modelType)
  
  console.log("OLD (JS calculation):", {
    statistic: oldResult.statistic,
    pValue: oldResult.pValue,
    isStationary: oldResult.isStationary
  })
  
  console.log("NEW (WASM calculation):", {
    statistic: newResult.statistic,
    pValue: newResult.pValue,
    isStationary: newResult.isStationary,
    optimalLags: newResult.optimalLags,
    aicValue: newResult.aicValue
  })
  
  const statisticDiff = Math.abs(newResult.statistic - oldResult.statistic)
  const pValueDiff = Math.abs(newResult.pValue - oldResult.pValue)
  
  console.log("DIFFERENCES:", {
    statisticDifference: statisticDiff,
    pValueDifference: pValueDiff,
    stationarityAgreement: oldResult.isStationary === newResult.isStationary
  })
  
  return { oldResult, newResult, statisticDiff, pValueDiff }
}

// Updated worker message handler
self.onmessage = async (event) => {
  const {
    type,
    data: { pricesA, pricesB },
    params,
    selectedPair,
  } = event.data

  if (type === "runAnalysis") {
    await initializeWasm()

    const { modelType, /* ... other params ... */ } = params

    try {
      // ... existing analysis code ...

      // Use the ENHANCED WASM function for better accuracy
      const seriesForADF = modelType === "ratio" ? ratios : modelType === "euclidean" ? distances : spreads
      const seriesTypeForADF = modelType === "ratio" ? "ratios" : modelType === "euclidean" ? "distances" : "spreads"
      
      // NEW: Use complete WASM calculation
      const adfResults = await adfTestNewWay(seriesForADF, seriesTypeForADF, modelType)

      // Optional: Compare with old method for debugging
      if (process.env.NODE_ENV === 'development') {
        await compareAdfMethods(seriesForADF, seriesTypeForADF, modelType)
      }

      // ... rest of analysis code ...

      const analysisData = {
        // ... existing properties ...
        statistics: {
          // ... existing statistics ...
          adfResults,
          // ... rest of statistics ...
        },
        // ... rest of analysis data ...
      }

      self.postMessage({ type: "analysisComplete", analysisData, error: "" })

    } catch (e) {
      console.error("Error in enhanced analysis worker:", e)
      self.postMessage({ type: "analysisComplete", analysisData: null, error: e.message })
    }
  }
}

// Export for use in other modules
export { 
  adfTestOldWay, 
  adfTestNewWay, 
  compareAdfMethods,
  initializeWasm
}