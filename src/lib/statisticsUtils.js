/**
 * Statistical Calculation Utilities
 * 
 * Safe mathematical functions for analytics calculations
 * Handles edge cases: empty arrays, null values, infinity
 */

/**
 * Calculate the mean (average) of a numeric array
 * Handles empty arrays and invalid values safely
 */
export function calculateMean(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return 0;
  }
  
  const validValues = values
    .filter(v => typeof v === 'number' && isFinite(v))
    .map(v => Number(v));
  
  if (validValues.length === 0) {
    return 0;
  }
  
  const sum = validValues.reduce((acc, val) => acc + val, 0);
  return sum / validValues.length;
}

/**
 * Calculate the median of a numeric array
 * Handles empty arrays and invalid values safely
 */
export function calculateMedian(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return 0;
  }
  
  const validValues = values
    .filter(v => typeof v === 'number' && isFinite(v))
    .map(v => Number(v))
    .sort((a, b) => a - b);
  
  if (validValues.length === 0) {
    return 0;
  }
  
  const mid = Math.floor(validValues.length / 2);
  
  if (validValues.length % 2 === 0) {
    // Even number of elements: average of two middle values
    return (validValues[mid - 1] + validValues[mid]) / 2;
  } else {
    // Odd number of elements: middle value
    return validValues[mid];
  }
}

/**
 * Calculate the mode (most common value) of a numeric array
 * Returns the first mode if there are multiple modes
 * Handles empty arrays and invalid values safely
 */
export function calculateMode(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return 0;
  }
  
  const validValues = values
    .filter(v => typeof v === 'number' && isFinite(v))
    .map(v => Number(v));
  
  if (validValues.length === 0) {
    return 0;
  }
  
  // Count frequency of each value
  const frequency = {};
  let maxFrequency = 0;
  let mode = validValues[0];
  
  for (const value of validValues) {
    frequency[value] = (frequency[value] || 0) + 1;
    
    if (frequency[value] > maxFrequency) {
      maxFrequency = frequency[value];
      mode = value;
    }
  }
  
  return mode;
}

/**
 * Calculate standard deviation of a numeric array
 * Handles empty arrays and invalid values safely
 */
export function calculateStandardDeviation(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return 0;
  }
  
  const validValues = values
    .filter(v => typeof v === 'number' && isFinite(v))
    .map(v => Number(v));
  
  if (validValues.length === 0) {
    return 0;
  }
  
  const mean = calculateMean(validValues);
  const squaredDifferences = validValues.map(v => Math.pow(v - mean, 2));
  const variance = squaredDifferences.reduce((sum, val) => sum + val, 0) / validValues.length;
  
  return Math.sqrt(variance);
}

/**
 * Calculate percentile of a numeric array
 * @param {number[]} values - Array of numeric values
 * @param {number} percentile - Percentile to calculate (0-100)
 */
export function calculatePercentile(values, percentile) {
  if (!Array.isArray(values) || values.length === 0 || percentile < 0 || percentile > 100) {
    return 0;
  }
  
  const validValues = values
    .filter(v => typeof v === 'number' && isFinite(v))
    .map(v => Number(v))
    .sort((a, b) => a - b);
  
  if (validValues.length === 0) {
    return 0;
  }
  
  const index = (percentile / 100) * (validValues.length - 1);
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  const weight = index - lower;
  
  if (lower === upper) {
    return validValues[lower];
  }
  
  return validValues[lower] * (1 - weight) + validValues[upper] * weight;
}

/**
 * Calculate sum of a numeric array
 * Handles empty arrays and invalid values safely
 */
export function calculateSum(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return 0;
  }
  
  return values
    .filter(v => typeof v === 'number' && isFinite(v))
    .map(v => Number(v))
    .reduce((sum, val) => sum + val, 0);
}

/**
 * Find max value in a numeric array
 * Handles empty arrays and invalid values safely
 */
export function calculateMax(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return 0;
  }
  
  const validValues = values
    .filter(v => typeof v === 'number' && isFinite(v))
    .map(v => Number(v));
  
  if (validValues.length === 0) {
    return 0;
  }
  
  return Math.max(...validValues);
}

/**
 * Find min value in a numeric array
 * Handles empty arrays and invalid values safely
 */
export function calculateMin(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return 0;
  }
  
  const validValues = values
    .filter(v => typeof v === 'number' && isFinite(v))
    .map(v => Number(v));
  
  if (validValues.length === 0) {
    return 0;
  }
  
  return Math.min(...validValues);
}

/**
 * Calculate growth percentage between two values
 * Handles edge cases like zero baseline
 */
export function calculateGrowthPercentage(currentValue, previousValue) {
  if (previousValue === 0) {
    return currentValue > 0 ? 100 : 0;
  }
  
  return ((currentValue - previousValue) / previousValue) * 100;
}

/**
 * Format currency for display
 */
export function formatCurrency(value, currency = '₱') {
  const num = Number(value) || 0;
  return `${currency}${num.toFixed(2)}`;
}

/**
 * Format number with commas for display
 */
export function formatNumber(value) {
  const num = Number(value) || 0;
  return num.toLocaleString('en-US', { maximumFractionDigits: 2 });
}
