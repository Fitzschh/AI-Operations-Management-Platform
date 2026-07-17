/**
 * Firebase Realtime Database Analytics API
 * 
 * This module provides functions to:
 * 1. Update analytics data when orders are created/completed
 * 2. Fetch analytics data for dashboard display
 * 3. Calculate statistical summaries
 * 4. Prevent duplicate analytics processing
 * 
 * Database Structure:
 * {branchId}/analytics/
 *   ├── summary/ (total orders, revenue, averages)
 *   ├── products/ (per-item sales data)
 *   ├── hourly/ (orders and revenue by hour)
 *   ├── daily/ (orders and revenue by day)
 *   ├── weekly/ (orders and revenue by week)
 *   ├── monthly/ (orders and revenue by month)
 *   ├── topProducts/ (ranked product performance)
 *   ├── aiInsights/ (reserved for saved AI analysis)
 *   ├── processedOrders/ (persistent idempotency ledger)
 *   └── statistics/ (calculated means, medians, etc.)
 */

import { database } from './firebase';
import { ref, get, set, update, runTransaction, onValue, off } from 'firebase/database';
import { calculateMean, calculateMedian, calculateMode } from './statisticsUtils';

/**
 * Helper to construct analytics paths
 */
function analyticsPath(branchId, path) {
  return `${branchId}/analytics${path ? '/' + path : ''}`;
}

function createEmptyAnalytics() {
  return {
    summary: {
      totalOrders: 0,
      totalRevenue: 0,
      averageOrderValue: 0,
      bestSellingItem: '',
      leastSellingItem: '',
      lastUpdated: new Date().toISOString(),
    },
    products: {},
    hourly: {},
    daily: {},
    weekly: {},
    monthly: {},
    topProducts: {},
    aiInsights: {},
    processedOrders: {},
    meta: {
      processedOrderLedgerInitialized: false,
    },
    statistics: {
      ordersPerDay: { mean: 0, median: 0, mode: 0 },
      revenuePerDay: { mean: 0, median: 0 },
    },
  };
}

/**
 * Initialize analytics structure for a business if it doesn't exist
 */
export async function initializeAnalytics(branchId) {
  try {
    const analyticsRef = ref(database, analyticsPath(branchId));
    const snapshot = await get(analyticsRef);
    
    if (!snapshot.exists()) {
      // Use Firebase SDK set() instead of REST API to avoid auth-flow mismatches
      await set(analyticsRef, createEmptyAnalytics());
    }
  } catch (error) {
    console.error('Error initializing analytics:', error);
  }
}

/**
 * Check if an order has already been processed for analytics.
 * The analytics ledger is the source of truth because order logs can be deleted.
 */
async function isOrderAlreadyProcessed(branchId, orderId) {
  try {
    const processedRef = ref(database, analyticsPath(branchId, `processedOrders/${orderId}`));
    const snapshot = await get(processedRef);
    if (!snapshot.exists()) return false;
    return true;
  } catch (error) {
    console.error('Error checking if order was processed:', error);
    return false;
  }
}

/**
 * Mark an order as processed for analytics
 * Uses Firebase SDK update() for consistent auth with the transaction writes.
 */
async function markOrderAsProcessed(branchId, orderId) {
  try {
    const orderRef = ref(database, `${branchId}/logs/${orderId}`);
    await update(orderRef, {
      analyticsProcessed: true,
      analyticsProcessedAt: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Error marking order as processed:', error);
  }
}

/**
 * Format a date as YYYY-MM-DD
 */
export function formatDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Format a date as YYYY-MM
 */
export function formatMonthKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  return `${year}-${month}`;
}

/**
 * Get ISO week key (e.g., "2026-W24")
 */
export function formatWeekKey(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const weekNum = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
  const weekString = String(weekNum).padStart(2, '0');
  return `${d.getUTCFullYear()}-W${weekString}`;
}

/**
 * Get hour key (0-23)
 */
export function formatHourKey(date) {
  return String(date.getHours()).padStart(2, '0');
}

function getOrderDate(orderData) {
  const date = new Date(orderData.timestamp || orderData.createdAt || Date.now());
  return Number.isNaN(date.getTime()) ? new Date() : date;
}

function getOrderItems(orderData) {
  if (!orderData?.items) return [];
  return Array.isArray(orderData.items) ? orderData.items : Object.values(orderData.items);
}

// Firebase keys cannot contain . # $ [ ] / or control characters.
function sanitizeFirebaseKey(value) {
  if (!value) return value;
  const cleaned = String(value).trim().replace(/\s+/g, '_').replace(/[.#$[\]/\u0000-\u001F\u007F]/g, '_');
  return cleaned || null;
}

function getItemId(item) {
  return sanitizeFirebaseKey(
    item.itemId || item.id || item.key || item.name?.toLowerCase().trim().replace(/\s+/g, '_')
  );
}

export function isAnalyticsOrder(orderData) {
  if (!orderData || typeof orderData !== 'object') return false;
  if (orderData.analyticsExcluded === true) return false;
  const status = String(orderData.status || '').toLowerCase();
  if (['cancelled', 'canceled', 'void', 'voided', 'refunded', 'deleted'].includes(status)) {
    return false;
  }
  return getOrderItems(orderData).length > 0 || orderData.total !== undefined;
}

function getOrderTotal(orderData, items) {
  if (orderData.total !== undefined && orderData.total !== null) {
    return Number(orderData.total || 0);
  }

  return items.reduce((sum, item) => {
    const qty = Number(item.quantity || 1);
    const subtotal = Number(item.subtotal || (Number(item.price || 0) * qty) || 0);
    return sum + subtotal;
  }, 0);
}

function applyOrderToAnalytics(analytics, orderData) {
  const items = getOrderItems(orderData);
  const orderTotal = getOrderTotal(orderData, items);
  const orderDate = getOrderDate(orderData);
  const dateKey = formatDateKey(orderDate);
  const monthKey = formatMonthKey(orderDate);
  const weekKey = formatWeekKey(orderDate);
  const hourKey = formatHourKey(orderDate);

  analytics.summary.totalOrders = Number(analytics.summary.totalOrders || 0) + 1;
  analytics.summary.totalRevenue = Number((Number(analytics.summary.totalRevenue || 0) + orderTotal).toFixed(2));

  if (!analytics.hourly[dateKey]) analytics.hourly[dateKey] = {};
  if (!analytics.hourly[dateKey][hourKey]) analytics.hourly[dateKey][hourKey] = { orders: 0, revenue: 0 };
  analytics.hourly[dateKey][hourKey].orders = Number(analytics.hourly[dateKey][hourKey].orders || 0) + 1;
  analytics.hourly[dateKey][hourKey].revenue = Number((Number(analytics.hourly[dateKey][hourKey].revenue || 0) + orderTotal).toFixed(2));

  if (!analytics.daily[dateKey]) analytics.daily[dateKey] = { orders: 0, revenue: 0, averageOrderValue: 0 };
  analytics.daily[dateKey].orders = Number(analytics.daily[dateKey].orders || 0) + 1;
  analytics.daily[dateKey].revenue = Number((Number(analytics.daily[dateKey].revenue || 0) + orderTotal).toFixed(2));
  analytics.daily[dateKey].averageOrderValue = Number((analytics.daily[dateKey].revenue / analytics.daily[dateKey].orders).toFixed(2));

  if (!analytics.weekly[weekKey]) analytics.weekly[weekKey] = { orders: 0, revenue: 0 };
  analytics.weekly[weekKey].orders = Number(analytics.weekly[weekKey].orders || 0) + 1;
  analytics.weekly[weekKey].revenue = Number((Number(analytics.weekly[weekKey].revenue || 0) + orderTotal).toFixed(2));

  if (!analytics.monthly[monthKey]) analytics.monthly[monthKey] = { orders: 0, revenue: 0 };
  analytics.monthly[monthKey].orders = Number(analytics.monthly[monthKey].orders || 0) + 1;
  analytics.monthly[monthKey].revenue = Number((Number(analytics.monthly[monthKey].revenue || 0) + orderTotal).toFixed(2));

  for (const item of items) {
    const itemId = getItemId(item);
    if (!itemId) continue;

    const qty = Number(item.quantity || 1);
    const subtotal = Number(item.subtotal || (Number(item.price || 0) * qty) || 0);

    if (!analytics.products[itemId]) {
      analytics.products[itemId] = {
        name: item.name || itemId,
        quantitySold: 0,
        revenue: 0,
        orderCount: 0,
      };
    }

    analytics.products[itemId].quantitySold = Number(analytics.products[itemId].quantitySold || 0) + qty;
    analytics.products[itemId].revenue = Number((Number(analytics.products[itemId].revenue || 0) + subtotal).toFixed(2));
    analytics.products[itemId].orderCount = Number(analytics.products[itemId].orderCount || 0) + 1;
  }
}

function buildAnalyticsFromLogs(logsData = {}) {
  const analytics = createEmptyAnalytics();
  const now = new Date().toISOString();
  const orders = Object.entries(logsData || {})
    .filter(([, orderData]) => isAnalyticsOrder(orderData))
    .sort(([, a], [, b]) => getOrderDate(a) - getOrderDate(b));

  for (const [orderId, orderData] of orders) {
    const items = getOrderItems(orderData);
    const orderDate = getOrderDate(orderData);
    applyOrderToAnalytics(analytics, orderData);
    analytics.processedOrders[orderId] = {
      orderId,
      processedAt: orderData.analyticsProcessedAt || now,
      orderDate: orderDate.toISOString(),
      total: Number(getOrderTotal(orderData, items).toFixed(2)),
      rebuiltFromLogs: true,
    };
  }

  analytics.meta = {
    ...(analytics.meta || {}),
    processedOrderLedgerInitialized: true,
    processedOrderLedgerInitializedAt: analytics.meta?.processedOrderLedgerInitializedAt || now,
    lastRebuiltAt: now,
  };

  return updateDerivedAnalytics(analytics);
}

async function getRecordedOrdersData(branchId) {
  const [logsSnapshot, deletedLogsSnapshot] = await Promise.all([
    get(ref(database, `${branchId}/logs`)),
    get(ref(database, `${branchId}/deletedLogs`)),
  ]);

  return {
    ...(deletedLogsSnapshot.val() || {}),
    ...(logsSnapshot.val() || {}),
  };
}

function normalizeAnalytics(current) {
  const defaults = createEmptyAnalytics();
  const data = current && typeof current === 'object' ? current : {};

  return {
    ...defaults,
    ...data,
    summary: { ...defaults.summary, ...(data.summary || {}) },
    products: data.products || {},
    hourly: data.hourly || {},
    daily: data.daily || {},
    weekly: data.weekly || {},
    monthly: data.monthly || {},
    topProducts: data.topProducts || {},
    aiInsights: data.aiInsights || {},
    processedOrders: data.processedOrders || {},
    meta: { ...defaults.meta, ...(data.meta || {}) },
    statistics: {
      ordersPerDay: {
        ...defaults.statistics.ordersPerDay,
        ...(data.statistics?.ordersPerDay || {}),
      },
      revenuePerDay: {
        ...defaults.statistics.revenuePerDay,
        ...(data.statistics?.revenuePerDay || {}),
      },
    },
  };
}

function updateDerivedAnalytics(analytics) {
  const productEntries = Object.entries(analytics.products);
  if (productEntries.length > 0) {
    const bestSeller = productEntries.reduce((a, b) => (
      b[1].quantitySold > a[1].quantitySold ? b : a
    ));
    const leastSeller = productEntries.reduce((a, b) => (
      b[1].quantitySold < a[1].quantitySold ? b : a
    ));
    analytics.summary.bestSellingItem = bestSeller[0];
    analytics.summary.leastSellingItem = leastSeller[0];
    analytics.topProducts = Object.fromEntries(
      productEntries
        .sort((a, b) => (b[1].quantitySold || 0) - (a[1].quantitySold || 0))
        .slice(0, 10)
    );
  } else {
    analytics.summary.bestSellingItem = '';
    analytics.summary.leastSellingItem = '';
    analytics.topProducts = {};
  }

  analytics.summary.averageOrderValue = analytics.summary.totalOrders > 0
    ? Number((analytics.summary.totalRevenue / analytics.summary.totalOrders).toFixed(2))
    : 0;
  analytics.summary.lastUpdated = new Date().toISOString();

  const dailyEntries = Object.values(analytics.daily);
  if (dailyEntries.length > 0) {
    const dailyOrders = dailyEntries.map(d => d.orders || 0);
    const dailyRevenues = dailyEntries.map(d => d.revenue || 0);
    analytics.statistics = {
      ordersPerDay: {
        mean: Number(calculateMean(dailyOrders).toFixed(2)),
        median: Number(calculateMedian(dailyOrders).toFixed(2)),
        mode: calculateMode(dailyOrders),
      },
      revenuePerDay: {
        mean: Number(calculateMean(dailyRevenues).toFixed(2)),
        median: Number(calculateMedian(dailyRevenues).toFixed(2)),
      },
    };
  } else {
    analytics.statistics = {
      ordersPerDay: { mean: 0, median: 0, mode: 0 },
      revenuePerDay: { mean: 0, median: 0 },
    };
  }

  return analytics;
}

/**
 * One-time migration helper for branches that already had analytics before the
 * persistent processedOrders ledger existed. If analytics already has totals,
 * the current operational logs are treated as already represented so the new
 * incremental processor does not double-count them.
 */
export async function initializeProcessedOrderLedger(branchId, logsData = {}) {
  const analyticsRef = ref(database, analyticsPath(branchId));
  const now = new Date().toISOString();

  await runTransaction(analyticsRef, (current) => {
    const analytics = normalizeAnalytics(current);
    const hasLedger = Object.keys(analytics.processedOrders || {}).length > 0;
    const ledgerInitialized = analytics.meta?.processedOrderLedgerInitialized === true;

    if (hasLedger || ledgerInitialized) {
      return analytics;
    }

    const existingOrderCount = Number(analytics.summary?.totalOrders || 0);
    const eligibleOrders = Object.entries(logsData || {})
      .filter(([, orderData]) => isAnalyticsOrder(orderData));
    const lastUpdatedDate = new Date(analytics.summary?.lastUpdated || '');
    const hasValidLastUpdated = !Number.isNaN(lastUpdatedDate.getTime());

    if (existingOrderCount > 0) {
      for (const [orderId, orderData] of eligibleOrders) {
        const orderDate = getOrderDate(orderData);
        const shouldSeedAsExisting = orderData.analyticsProcessed === true
          || (hasValidLastUpdated && orderDate <= lastUpdatedDate)
          || (!hasValidLastUpdated && eligibleOrders.length <= existingOrderCount);

        if (!shouldSeedAsExisting) continue;

        const items = getOrderItems(orderData);
        analytics.processedOrders[orderId] = {
          orderId,
          processedAt: orderData.analyticsProcessedAt || now,
          orderDate: orderDate.toISOString(),
          total: getOrderTotal(orderData, items),
          migratedFromExistingAnalytics: true,
        };
      }
    }

    analytics.meta = {
      ...(analytics.meta || {}),
      processedOrderLedgerInitialized: true,
      processedOrderLedgerInitializedAt: now,
    };

    return analytics;
  });
}

/**
 * Process a single completed order and update analytics
 * This function uses transactions to ensure data consistency
 */
export async function processOrderAnalytics(branchId, orderId, orderData) {
  try {
    if (!isAnalyticsOrder(orderData)) return;

    // Ensure analytics structure exists
    await initializeAnalytics(branchId);
    
    // Check if already processed
    const alreadyProcessed = await isOrderAlreadyProcessed(branchId, orderId);
    if (alreadyProcessed) {
      console.log(`Order ${orderId} already processed for analytics, skipping.`);
      return;
    }
    
    const orderDate = getOrderDate(orderData);
    
    // Extract order values
    const items = getOrderItems(orderData);
    const orderTotal = getOrderTotal(orderData, items);
    
    // Use transactions for atomic updates of counters
    const analyticsRef = ref(database, analyticsPath(branchId));
    
    await runTransaction(analyticsRef, (current) => {
      const analytics = normalizeAnalytics(current);

      if (analytics.processedOrders?.[orderId]) {
        return analytics;
      }

      applyOrderToAnalytics(analytics, orderData);

      analytics.processedOrders[orderId] = {
        orderId,
        processedAt: new Date().toISOString(),
        orderDate: orderDate.toISOString(),
        total: Number(orderTotal.toFixed(2)),
      };
      
      return updateDerivedAnalytics(analytics);
    });
    
    // Mark order as processed
    await markOrderAsProcessed(branchId, orderId);
    
    console.log(`Analytics updated for order ${orderId}`);
  } catch (error) {
    console.error('Error processing order analytics:', error);
    throw error;
  }
}

export async function rebuildAnalyticsFromLogs(branchId, logsData = null) {
  if (!branchId) return;

  const logs = logsData || await getRecordedOrdersData(branchId);
  const analytics = buildAnalyticsFromLogs(logs);
  await set(ref(database, analyticsPath(branchId)), analytics);
}

export async function excludeOrderFromAnalytics(branchId, orderId, reason = 'Manual analytics correction') {
  if (!branchId || !orderId) return;

  const now = new Date().toISOString();
  const activeOrderSnapshot = await get(ref(database, `${branchId}/logs/${orderId}`));
  const orderPath = activeOrderSnapshot.exists()
    ? `${branchId}/logs/${orderId}`
    : `${branchId}/deletedLogs/${orderId}`;
  const orderRef = ref(database, orderPath);
  await update(orderRef, {
    analyticsExcluded: true,
    analyticsExcludedAt: now,
    analyticsExcludedReason: reason || 'Manual analytics correction',
  });

  await rebuildAnalyticsFromLogs(branchId);
}

export async function includeOrderInAnalytics(branchId, orderId) {
  if (!branchId || !orderId) return;

  const activeOrderSnapshot = await get(ref(database, `${branchId}/logs/${orderId}`));
  const orderPath = activeOrderSnapshot.exists()
    ? `${branchId}/logs/${orderId}`
    : `${branchId}/deletedLogs/${orderId}`;
  const orderRef = ref(database, orderPath);
  await update(orderRef, {
    analyticsExcluded: false,
    analyticsExcludedAt: null,
    analyticsExcludedReason: null,
  });

  await rebuildAnalyticsFromLogs(branchId);
}

/**
 * Fetch current analytics summary for dashboard
 */
export async function getAnalyticsSummary(branchId) {
  try {
    const ref_db = ref(database, analyticsPath(branchId, 'summary'));
    const snapshot = await get(ref_db);
    
    if (!snapshot.exists()) {
      return {
        totalOrders: 0,
        totalRevenue: 0,
        averageOrderValue: 0,
        bestSellingItem: '',
        leastSellingItem: '',
        lastUpdated: '',
      };
    }
    
    return snapshot.val();
  } catch (error) {
    console.error('Error fetching analytics summary:', error);
    return {
      totalOrders: 0,
      totalRevenue: 0,
      averageOrderValue: 0,
      bestSellingItem: '',
      leastSellingItem: '',
      lastUpdated: '',
    };
  }
}

/**
 * Fetch products analytics
 */
export async function getProductsAnalytics(branchId) {
  try {
    const ref_db = ref(database, analyticsPath(branchId, 'products'));
    const snapshot = await get(ref_db);
    
    if (!snapshot.exists()) {
      return {};
    }
    
    return snapshot.val();
  } catch (error) {
    console.error('Error fetching products analytics:', error);
    return {};
  }
}

/**
 * Fetch daily analytics
 */
export async function getDailyAnalytics(branchId) {
  try {
    const ref_db = ref(database, analyticsPath(branchId, 'daily'));
    const snapshot = await get(ref_db);
    
    if (!snapshot.exists()) {
      return {};
    }
    
    return snapshot.val();
  } catch (error) {
    console.error('Error fetching daily analytics:', error);
    return {};
  }
}

/**
 * Fetch hourly analytics for a specific date
 */
export async function getHourlyAnalytics(branchId, dateKey) {
  try {
    const ref_db = ref(database, analyticsPath(branchId, `hourly/${dateKey}`));
    const snapshot = await get(ref_db);
    
    if (!snapshot.exists()) {
      return {};
    }
    
    return snapshot.val();
  } catch (error) {
    console.error('Error fetching hourly analytics:', error);
    return {};
  }
}

/**
 * Fetch weekly analytics
 */
export async function getWeeklyAnalytics(branchId) {
  try {
    const ref_db = ref(database, analyticsPath(branchId, 'weekly'));
    const snapshot = await get(ref_db);
    
    if (!snapshot.exists()) {
      return {};
    }
    
    return snapshot.val();
  } catch (error) {
    console.error('Error fetching weekly analytics:', error);
    return {};
  }
}

/**
 * Fetch monthly analytics
 */
export async function getMonthlyAnalytics(branchId) {
  try {
    const ref_db = ref(database, analyticsPath(branchId, 'monthly'));
    const snapshot = await get(ref_db);
    
    if (!snapshot.exists()) {
      return {};
    }
    
    return snapshot.val();
  } catch (error) {
    console.error('Error fetching monthly analytics:', error);
    return {};
  }
}

/**
 * Fetch statistics (calculated aggregates)
 */
export async function getStatistics(branchId) {
  try {
    const ref_db = ref(database, analyticsPath(branchId, 'statistics'));
    const snapshot = await get(ref_db);
    
    if (!snapshot.exists()) {
      return {
        ordersPerDay: { mean: 0, median: 0, mode: 0 },
        revenuePerDay: { mean: 0, median: 0 },
      };
    }
    
    return snapshot.val();
  } catch (error) {
    console.error('Error fetching statistics:', error);
    return {
      ordersPerDay: { mean: 0, median: 0, mode: 0 },
      revenuePerDay: { mean: 0, median: 0 },
    };
  }
}

/**
 * Get orders for today
 */
export async function getTodayAnalytics(branchId) {
  const today = formatDateKey(new Date());
  try {
    const ref_db = ref(database, analyticsPath(branchId, `daily/${today}`));
    const snapshot = await get(ref_db);
    
    if (!snapshot.exists()) {
      return { orders: 0, revenue: 0, averageOrderValue: 0 };
    }
    
    return snapshot.val();
  } catch (error) {
    console.error('Error fetching today analytics:', error);
    return { orders: 0, revenue: 0, averageOrderValue: 0 };
  }
}

/**
 * Get current week's analytics
 */
export async function getCurrentWeekAnalytics(branchId) {
  const weekKey = formatWeekKey(new Date());
  try {
    const ref_db = ref(database, analyticsPath(branchId, `weekly/${weekKey}`));
    const snapshot = await get(ref_db);
    
    if (!snapshot.exists()) {
      return { orders: 0, revenue: 0 };
    }
    
    return snapshot.val();
  } catch (error) {
    console.error('Error fetching current week analytics:', error);
    return { orders: 0, revenue: 0 };
  }
}

/**
 * Get current month's analytics
 */
export async function getCurrentMonthAnalytics(branchId) {
  const monthKey = formatMonthKey(new Date());
  try {
    const ref_db = ref(database, analyticsPath(branchId, `monthly/${monthKey}`));
    const snapshot = await get(ref_db);
    
    if (!snapshot.exists()) {
      return { orders: 0, revenue: 0 };
    }
    
    return snapshot.val();
  } catch (error) {
    console.error('Error fetching current month analytics:', error);
    return { orders: 0, revenue: 0 };
  }
}

export function onAnalyticsSummaryChange(branchId, callback) {
  const summaryRef = ref(database, analyticsPath(branchId, 'summary'));
  const handler = (snapshot) => {
    callback(snapshot.val() || {
      totalOrders: 0,
      totalRevenue: 0,
      averageOrderValue: 0,
      bestSellingItem: '',
      leastSellingItem: '',
      lastUpdated: '',
    });
  };
  onValue(summaryRef, handler);
  return () => off(summaryRef, 'value', handler);
}

/**
 * Real-time listener for the full analytics document.
 * Prefer this on dashboard screens to avoid many parallel Firebase reads/listeners.
 */
export function onAnalyticsChange(branchId, callback) {
  const analyticsRef = ref(database, analyticsPath(branchId));
  const handler = (snapshot) => {
    callback(normalizeAnalytics(snapshot.val()));
  };
  onValue(analyticsRef, handler);
  return () => off(analyticsRef, 'value', handler);
}

/**
 * Real-time listener for products analytics
 */
export function onProductsAnalyticsChange(branchId, callback) {
  const productsRef = ref(database, analyticsPath(branchId, 'products'));
  const handler = (snapshot) => {
    callback(snapshot.val() || {});
  };
  onValue(productsRef, handler);
  return () => off(productsRef, 'value', handler);
}

/**
 * Real-time listener for daily analytics
 */
export function onDailyAnalyticsChange(branchId, callback) {
  const dailyRef = ref(database, analyticsPath(branchId, 'daily'));
  const handler = (snapshot) => {
    callback(snapshot.val() || {});
  };
  onValue(dailyRef, handler);
  return () => off(dailyRef, 'value', handler);
}

/**
 * Real-time listener for hourly analytics on a specific date
 */
export function onHourlyAnalyticsChange(branchId, dateKey, callback) {
  const hourlyRef = ref(database, analyticsPath(branchId, `hourly/${dateKey}`));
  const handler = (snapshot) => {
    callback(snapshot.val() || {});
  };
  onValue(hourlyRef, handler);
  return () => off(hourlyRef, 'value', handler);
}

/**
 * Real-time listener for weekly analytics
 */
export function onWeeklyAnalyticsChange(branchId, callback) {
  const weeklyRef = ref(database, analyticsPath(branchId, 'weekly'));
  const handler = (snapshot) => {
    callback(snapshot.val() || {});
  };
  onValue(weeklyRef, handler);
  return () => off(weeklyRef, 'value', handler);
}

/**
 * Real-time listener for monthly analytics
 */
export function onMonthlyAnalyticsChange(branchId, callback) {
  const monthlyRef = ref(database, analyticsPath(branchId, 'monthly'));
  const handler = (snapshot) => {
    callback(snapshot.val() || {});
  };
  onValue(monthlyRef, handler);
  return () => off(monthlyRef, 'value', handler);
}
