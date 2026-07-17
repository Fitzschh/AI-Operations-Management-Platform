import { pilotAiConfig } from './pilotAiConfig';
import { buildSystemPrompt, buildDataPrompt, parseModelJson } from './aiPrompts';

const CACHE_KEY_PREFIX = 'ai_analyst_cache_v2_';
const CACHE_DURATION_MS = 30 * 60 * 1000;

function getCacheKey(branchId, mode) {
  return `${CACHE_KEY_PREFIX}${branchId}_${mode}`;
}

function normalizeAnalysisMode(mode) {
  if (mode === 'deep') return 'deep';
  if (mode === 'executive') return 'executive';
  if (mode === 'live') return 'live';
  if (mode === 'briefing') return 'briefing';
  if (mode === 'leak') return 'leak';
  if (mode === 'simulation') return 'simulation';
  if (mode === 'opschat') return 'opschat';
  return 'realtime';
}

async function requestAnalysis(analyticsData, mode, branchId) {
  const { apiKey, model, endpoint } = pilotAiConfig;

  if (!apiKey) {
    throw new Error('OpenAI API key is not configured. Add VITE_OPENAI_API_KEY to .env.local.');
  }

  const systemPrompt = buildSystemPrompt(mode);
  const dataPrompt = buildDataPrompt(analyticsData, mode);

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: dataPrompt },
      ],
      response_format: { type: 'json_object' },
      max_tokens: ['deep', 'executive', 'briefing', 'leak', 'simulation', 'opschat'].includes(mode) ? 2600 : 350,
      temperature: ['deep', 'executive', 'briefing', 'leak', 'simulation', 'opschat'].includes(mode) ? 0.45 : 0.35,
    }),
  });

  if (!response.ok) {
    let errorDetail = '';
    try {
      const errData = await response.json();
      errorDetail = errData?.error?.message || JSON.stringify(errData);
    } catch {
      errorDetail = `HTTP ${response.status}`;
    }
    console.error('[AI Analysis] OpenAI API error:', errorDetail);
    throw new Error(`AI analysis failed: ${errorDetail}`);
  }

  const data = await response.json();
  const rawContent = data.choices?.[0]?.message?.content;

  if (!rawContent) {
    throw new Error('AI returned an empty response.');
  }

  return parseModelJson(rawContent);
}

function getCachedAnalysis(branchId, mode) {
  try {
    const key = getCacheKey(branchId, mode);
    const cached = localStorage.getItem(key);
    if (!cached) return null;

    const parsed = JSON.parse(cached);
    const age = Date.now() - (parsed.timestamp || 0);

    if (age > CACHE_DURATION_MS) {
      localStorage.removeItem(key);
      return null;
    }

    return parsed.analysis;
  } catch {
    return null;
  }
}

function cacheAnalysis(branchId, mode, analysis) {
  try {
    const key = getCacheKey(branchId, mode);
    localStorage.setItem(key, JSON.stringify({
      timestamp: Date.now(),
      analysis,
    }));
  } catch {
  }
}

function normalizeName(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ');
}

function buildActiveProductIndex(inventory = {}) {
  const ids = new Set();
  const names = new Set();

  Object.entries(inventory || {}).forEach(([id, item]) => {
    ids.add(String(id));
    names.add(normalizeName(id));
    names.add(normalizeName(item?.productName || item?.name || item?.title));
  });

  names.delete('');

  return { ids, names };
}

function isActiveProduct(productId, product, activeIndex) {
  return activeIndex.ids.has(String(productId)) ||
    activeIndex.names.has(normalizeName(productId)) ||
    activeIndex.names.has(normalizeName(product?.name || product?.productName || product?.title));
}

function sanitizeAnalyticsForAI(analyticsData = {}) {
  const inventory = analyticsData.inventory || {};
  const activeIndex = buildActiveProductIndex(inventory);

  if (activeIndex.ids.size === 0 && activeIndex.names.size === 0) {
    return analyticsData;
  }

  const products = Object.fromEntries(
    Object.entries(analyticsData.products || {})
      .filter(([productId, product]) => isActiveProduct(productId, product, activeIndex))
  );

  const productEntries = Object.entries(products);
  const summary = { ...(analyticsData.summary || {}) };

  if (!isActiveProduct(summary.bestSellingItem, { name: summary.bestSellingItem }, activeIndex)) {
    const bestActive = productEntries
      .sort(([, a], [, b]) => Number(b.quantitySold || 0) - Number(a.quantitySold || 0))[0];
    summary.bestSellingItem = bestActive?.[1]?.name || bestActive?.[0] || '';
  }

  if (!isActiveProduct(summary.leastSellingItem, { name: summary.leastSellingItem }, activeIndex)) {
    const leastActive = productEntries
      .sort(([, a], [, b]) => Number(a.quantitySold || 0) - Number(b.quantitySold || 0))[0];
    summary.leastSellingItem = leastActive?.[1]?.name || leastActive?.[0] || '';
  }

  return {
    ...analyticsData,
    summary,
    products,
  };
}

export async function generateAIAnalysis(analyticsData, branchId, forceRefresh = false, mode = 'realtime') {
  const analysisMode = normalizeAnalysisMode(mode);
  const safeAnalyticsData = sanitizeAnalyticsForAI(analyticsData);

  if (!forceRefresh && branchId) {
    const cached = getCachedAnalysis(branchId, analysisMode);
    if (cached) {
      return { ...cached, fromCache: true };
    }
  }

  const analysis = await requestAnalysis(safeAnalyticsData, analysisMode, branchId);

  const defaultAnalysis = {
    mode: analysisMode,
    insight: null,
    greeting: '',
    overallHealth: '',
    topPerformers: '',
    concerns: '',
    shiftHandoff: null,
    quickWins: [],
    priorityActions: { urgent: [], recommended: [], longTerm: [] },
    closingNote: '',
    generatedAt: new Date().toISOString(),
    fromCache: false,
  };

  const result = { ...defaultAnalysis, ...analysis, generatedAt: new Date().toISOString(), fromCache: false };
  result.mode = normalizeAnalysisMode(result.mode || analysisMode);

  if (!result.priorityActions || typeof result.priorityActions !== 'object') {
    result.priorityActions = { urgent: [], recommended: [], longTerm: [] };
  }
  result.priorityActions.urgent = result.priorityActions.urgent || [];
  result.priorityActions.recommended = result.priorityActions.recommended || [];
  result.priorityActions.longTerm = result.priorityActions.longTerm || [];

  if (branchId) {
    cacheAnalysis(branchId, analysisMode, result);
  }

  return result;
}

export function clearAnalysisCache(branchId, mode = null) {
  try {
    if (mode) {
      localStorage.removeItem(getCacheKey(branchId, mode));
      return;
    }

    Object.keys(localStorage)
      .filter((key) => key.startsWith(`${CACHE_KEY_PREFIX}${branchId}_`))
      .forEach((key) => localStorage.removeItem(key));
  } catch {
  }
}
