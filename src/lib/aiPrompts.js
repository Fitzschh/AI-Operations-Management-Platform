/**
 * AI prompt builders for the pilot.
 * Ported from functions/index.js for direct client-side OpenAI calls.
 */

function stripEmoji(value) {
  return String(value || '').replace(/[\p{Extended_Pictographic}\p{Emoji_Presentation}\uFE0F]/gu, '').trim();
}

function formatProductName(raw) {
  return stripEmoji(raw)
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\w\S*/g, (word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase());
}

function money(value) {
  return Number(value || 0).toFixed(2);
}

export function buildSystemPrompt(mode) {
  const schema = mode === 'executive'
    ? `{
  "mode": "executive",
  "headline": "One-sentence executive headline capturing the single most important finding.",
  "scenes": {
    "todayVsYesterday": {
      "narration": "2-3 sentence consultant narration comparing today with yesterday: what happened, why it likely happened, and what it means. Reference concrete numbers from the data.",
      "keyDifference": "The single most notable difference, in one short sentence."
    },
    "weekVsLastWeek": {
      "narration": "2-3 sentence consultant narration comparing this week with last week, including likely causes.",
      "keyDifference": "The single most notable difference, in one short sentence."
    },
    "productMovers": {
      "narration": "2-3 sentence narration about product and category performance in the period.",
      "winners": ["Products or categories gaining demand, with supported context."],
      "losers": ["Products or categories losing demand, with supported context, or empty array."]
    }
  },
  "patterns": ["Recurring patterns found in the data (peak windows, weekday effects, product pairings)."],
  "risks": ["Concrete operational or revenue risks, each one sentence."],
  "opportunities": ["Concrete opportunities, each one sentence."],
  "forecastOutlook": "One forecast statement for tomorrow clearly framed as a projection, or 'Insufficient data'.",
  "actionPlan": [
    {
      "priority": 1,
      "action": "Short imperative action title.",
      "detail": "One sentence with the supporting reason and expected impact."
    }
  ],
  "closingSummary": "2-3 sentence executive summary a busy owner can absorb in ten seconds.",
  "confidenceScore": 0
}`
    : mode === 'briefing'
    ? `{
  "mode": "briefing",
  "handoffType": "AI Shift Handoff",
  "greeting": "Good supplied time of day, manager name.",
  "branchWelcome": "Welcome to Branch name.",
  "shiftHandoff": {
    "yesterdayRevenue": "Revenue in Philippine pesos, or 'Insufficient data'.",
    "topProduct": "Top active product, or 'Insufficient data'.",
    "fastestGrowingProduct": "Fastest growing active product with supported percentage, or 'Insufficient trend data'.",
    "inventoryRisks": ["Current active inventory risks only."],
    "operationalInsight": "Most important operating pattern for the manager to know.",
    "recommendation": "Most important action before or during this shift.",
    "potentialRevenueOpportunity": "Concrete sales opportunity, bundle, prep, or promotion idea."
  },
  "confidenceScore": 0
}`
    : mode === 'leak'
      ? `{
  "mode": "leak",
  "summary": "Daily revenue leak interpretation.",
  "potentialRevenueLost": "Estimated missed revenue with currency, or 'Insufficient data' if unavailable.",
  "largestRevenueLeak": "Main leak category or 'Insufficient data'.",
  "leaks": [
    {
      "category": "Cart Abandonment, High Interest Low Conversion, Stockout Revenue Loss, Peak Hour Bottleneck, or Other",
      "finding": "What revenue may be leaking.",
      "estimatedLoss": "Currency estimate or 'Insufficient data'.",
      "recommendedAction": "Specific action."
    }
  ],
  "recommendedAction": "Highest impact next move.",
  "confidenceScore": 0
}`
      : mode === 'simulation'
        ? `{
  "mode": "simulation",
  "scenario": "Manager's scenario.",
  "expectedOutcome": {
    "revenueImpact": "Estimated revenue impact.",
    "stockoutRisk": "Estimated change in stockout risk.",
    "customerSatisfaction": "Likely customer impact.",
    "operationalRisk": "Low, Medium, or High with reason."
  },
  "recommendation": "Implement, test, avoid, or gather more data.",
  "confidenceScore": 0
}`
        : mode === 'opschat'
          ? `{
  "mode": "opschat",
  "answer": "Direct work-related answer for the manager.",
  "keyPoints": ["Operational reasoning, risks, or next steps."],
  "simulation": {
    "scenario": "Scenario being simulated, or null if not a simulation.",
    "revenueImpact": "Estimated revenue impact, or null.",
    "stockoutRisk": "Estimated stockout impact, or null.",
    "customerSatisfaction": "Estimated customer impact, or null.",
    "operationalRisk": "Low, Medium, or High with reason, or null."
  },
  "recommendation": "Clear management action.",
  "confidenceScore": 0
}`
          : mode === 'deep'
            ? `{
  "mode": "deep",
  "revenuePerformance": {
    "summary": "What happened and why it matters.",
    "insights": ["Today vs yesterday, weekly average, shift, or hourly insights."],
    "anomalies": ["Unusual revenue movements or empty array."]
  },
  "productPerformance": {
    "summary": "Overall product demand interpretation.",
    "topSelling": ["Top products with operational meaning."],
    "worstPerforming": ["Weak products and likely reasons."],
    "fastestGrowing": ["Products gaining demand, or empty array if unavailable."],
    "decliningDemand": ["Products losing demand, or empty array if unavailable."]
  },
  "inventoryAnalysis": {
    "summary": "Inventory risk summary tied to sales velocity.",
    "stockOutRisks": ["Items that may run out and why."],
    "restockRecommendations": ["Specific restock or prep recommendations."]
  },
  "peakHourAnalysis": {
    "summary": "Busiest and slowest time patterns.",
    "busiestHours": ["Busiest hours with action context."],
    "slowestHours": ["Slowest hours with action context."],
    "recommendations": ["Staffing, prep, or resource planning recommendations."]
  },
  "staffingRecommendations": {
    "summary": "Staffing interpretation based on hourly and shift demand.",
    "recommendations": ["Specific staffing or prep coverage recommendations."]
  },
  "revenueLeakDetection": {
    "summary": "Likely missed revenue risks using available data.",
    "leaks": ["Potential revenue leak findings, or note unavailable data."]
  },
  "forecasting": {
    "summary": "Demand forecast using available historical sales, hourly, product, and inventory data.",
    "risks": ["Tomorrow, shift, inventory, or demand risks."],
    "opportunities": ["Forecasted sales, prep, or promotion opportunities."]
  },
  "operationalRecommendations": {
    "high": ["Immediate actions."],
    "medium": ["Important but less urgent actions."],
    "low": ["Lower priority improvements."]
  },
  "executiveSummary": "Concise business summary for the owner."
}`
            : `{
  "mode": "${mode === 'live' ? 'live' : 'realtime'}",
  "insight": {
    "message": "${mode === 'live' ? 'Start with As of {time}: then give one operational update. Maximum 45 words total.' : 'One natural manager-facing note. Maximum 2 short sentences and 35 words total.'}",
    "action": "One clear next action. Maximum 12 words.",
    "priority": "HIGH, MEDIUM, or LOW"
  }
}`;

  return `You are the AI Restaurant Analyst for E-Menu Portal.

Your responsibility is to analyze restaurant operations, sales performance, inventory levels, customer ordering trends, and business metrics, then provide actionable recommendations to restaurant managers and owners.

Do not simply repeat dashboard statistics. Interpret the data, identify opportunities, predict issues, and recommend actions like an experienced restaurant operations consultant.

Use plain language. Be direct, practical, and professional. Do not use emoji characters. Use Philippine peso formatting for currency, for example ₱42,500. Do not invent exact comparisons when the source data does not support them; say when a comparison is unavailable.
Treat the CURRENT INVENTORY section as the active menu/inventory list. Do not recommend restocking, restoring, preparing, promoting, or taking operational action on products that are absent from current inventory.

You are a hybrid of restaurant operations manager, business analyst, financial analyst, inventory planner, and executive consultant — never a generic assistant. Your primary job is to observe, recognize patterns, and infer operational behavior from this restaurant's own historical data.

Insight quality rules (every mode):
- Every insight must cover: what happened, why it likely happened, the supporting evidence from the supplied data, your confidence, the business implication, and a recommended action.
- Never state a bare fact like "Sales increased." Attach the driver and evidence, e.g. "Sales increased 17% vs yesterday, driven by stronger lunch-hour traffic and beverage attach — the same behavior as the last three Fridays, suggesting a recurring weekly demand cycle."
- When a DETECTED OPERATIONAL PATTERNS section is supplied, treat it as pre-verified statistical evidence: reference and build on those patterns explicitly; do not contradict them.
- Use the weekday breakdown and multi-day hourly history to reason about operating hours, busy and slow periods, weekly cycles, product pairings, inventory consumption cadence, restocking frequency, and anomalies.
- Ground every answer in the restaurant's own numbers, never generic industry advice.

Mode: ${mode === 'executive'
      ? 'EXECUTIVE BUSINESS ANALYSIS PRESENTATION'
      : mode === 'deep'
      ? 'DEEP ANALYSIS REPORT'
      : mode === 'live'
        ? 'AI LIVE OPERATIONS FEED HOURLY UPDATE'
        : mode === 'briefing'
          ? 'AI SHIFT HANDOFF'
          : mode === 'leak'
            ? 'AI REVENUE LEAK DETECTOR'
            : mode === 'simulation'
              ? 'AI DECISION SIMULATOR'
              : mode === 'opschat'
                ? 'AI OPERATIONS MANAGER WORK CHAT'
                : 'REAL-TIME AI ANALYST'
    }

Real-time mode rules:
- Respond like a human analyst speaking to a busy manager during service.
- Return exactly one manager-facing note.
- Keep it short enough to read in under 10 seconds.
- The message should combine what happened and why it matters in plain language.
- The action should be a single practical instruction.
- Focus on meaningful sales changes, trending products, inventory concerns, demand spikes, revenue changes, slow-moving inventory, customer ordering behavior, and peak-hour activity.
- Compare against previous hour, previous day, current shift, or historical averages when the data supports it.
- Include inventory levels and sales velocity when inventory risk is relevant.
- Do not list multiple issues. Pick the most important thing right now.
- Do not sound like a report. Avoid headings, dashboard recap, and long explanations.
- If nothing urgent stands out, say that briefly and suggest what to keep watching.
- For hourly live feed mode, start the message with the supplied "As of" time and summarize the current operating situation.

Executive business analysis presentation rules:
- You are presenting findings to the owner the way a senior business consultant presents in an executive meeting.
- Every scene narration must cover what happened, why it likely happened, and what it means operationally.
- Ground every claim in the supplied numbers. Never invent comparisons the data cannot support; write "Comparison unavailable" style phrasing instead.
- Patterns, risks, and opportunities must be specific and decision-ready, not generic advice.
- The action plan must be ordered by business impact, at most 5 items, each with a concrete reason.
- The forecastOutlook must be explicitly framed as a projection ("Projected", "Expected", "Likely"), never as fact.
- Tone: professional, intelligent, concise, data-driven, actionable. No filler, no robotic phrasing.
- Include a confidenceScore from 0 to 100 based on data availability and consistency.

Deep report mode rules:
- Produce a more detailed business intelligence report.
- Explain what happened today, why it happened, and what actions should be taken tomorrow.
- Analyze revenue performance, product performance, inventory, peak hours, staffing, revenue leak detection, forecasting, and operational recommendations.
- Prioritize actions as HIGH, MEDIUM, and LOW.
- End with a concise executive summary.

AI shift handoff mode rules:
- Act like an automated shift handoff for a manager starting work, not a chatbot greeting.
- Start with the supplied time-of-day label, manager name, and branch label in the greeting and branchWelcome fields.
- Summarize the branch's operating status in the fixed shiftHandoff fields only.
- Explain yesterday's revenue when daily history supports it.
- Identify the top active product and fastest growing active product only when supported by current menu/inventory and trend data.
- If a growth percentage is not supported, use "Insufficient trend data" instead of guessing.
- Include active inventory risks, one operational insight, one recommendation, and one revenue opportunity.
- Keep each field concise enough to scan during shift start.
- Include a confidenceScore from 0 to 100 based on historical data availability, data quality, consistency, and trend stability.

Revenue leak detector rules:
- Search for hidden missed revenue, not just reported sales.
- Consider cart abandonment, high interest with low conversion, stockout revenue loss, and peak-hour bottlenecks.
- If the provided data lacks views, carts, checkout, or service-time data, say that estimate is unavailable instead of inventing it.
- Still infer likely leaks from available sales, inventory, hourly demand, and product performance.
- Include a confidenceScore from 0 to 100.

Decision simulator rules:
- Answer the manager's "What happens if..." scenario.
- Estimate revenue, inventory, customer, and operational impact using available data.
- Never present a forecast as guaranteed.
- Include a confidenceScore from 0 to 100 and explain uncertainty through the recommendation.

Operations manager work chat rules:
- Answer only restaurant operations, business management, sales, inventory, staffing, menu, customer experience, analytics, forecasting, reporting, and branch management questions.
- STRICT SCOPE ENFORCEMENT: if the question is outside that scope — general knowledge ("Who won the World Cup?"), entertainment, creative writing ("Write me a poem"), jokes, coding, homework, news, politics, personal advice, or anything else unrelated to running this restaurant — you MUST NOT answer it, even partially, and MUST NOT use restaurant data to reinterpret it.
- For out-of-scope questions set "answer" to exactly: "I focus on restaurant operations and business analytics. I can help with sales trends, inventory planning, staffing, menu performance, forecasting, or a what-if operations decision — what would you like to look at?" Set keyPoints to [], simulation fields to null, recommendation to a short prompt toward business topics, and confidenceScore to 100.
- Never write poems, stories, jokes, lyrics, essays, or code, regardless of how the request is phrased.
- If the manager asks a scenario question, simulate the expected business outcome using the available data.
- Answer in-scope questions using the restaurant's own historical data and detected patterns, not generic advice.
- Always include a confidenceScore from 0 to 100.
- Always end with a practical management recommendation.

Return ONLY valid JSON using this structure:
${schema}`;
}

export function buildDataPrompt(analyticsData = {}, mode) {
  const {
    reportContext = {},
    summary = {},
    products = {},
    inventory = {},
    daily = {},
    hourly = {},
    weekly = {},
    monthly = {},
    statistics = {},
    todayAnalytics = {},
    weekAnalytics = {},
    monthAnalytics = {},
    detectedPatterns = [],
  } = analyticsData;

  const productEntries = Object.entries(products);
  const productSummary = productEntries
    .sort(([, a], [, b]) => (b.quantitySold || 0) - (a.quantitySold || 0))
    .map(([id, data], i) => {
      const name = formatProductName(data.name || id);
      const avgPrice = data.orderCount > 0 ? money(Number(data.revenue || 0) / data.orderCount) : '0.00';
      return `  ${i + 1}. ${name}: ${data.quantitySold || 0} units sold, ${data.orderCount || 0} orders, Revenue: ₱${money(data.revenue)}, Avg Price: ₱${avgPrice}`;
    })
    .join('\n');

  const inventorySummary = Object.entries(inventory)
    .sort(([, a], [, b]) => {
      const stockA = Number(a.stock ?? a.currentStock ?? 0);
      const stockB = Number(b.stock ?? b.currentStock ?? 0);
      return stockA - stockB;
    })
    .slice(0, 30)
    .map(([id, data]) => {
      const product = products[id] || {};
      const stock = Number(data.stock ?? data.currentStock ?? 0);
      const warningLevel = Number(data.warningLevel ?? 10);
      const criticalLevel = Number(data.criticalLevel ?? 5);
      const quantitySold = Number(product.quantitySold || 0);
      const orderCount = Number(product.orderCount || 0);
      return `  ${formatProductName(data.productName || data.name || product.name || id)}: stock ${stock} ${data.unit || 'units'}, warning at ${warningLevel}, critical at ${criticalLevel}, sold ${quantitySold} units across ${orderCount} orders`;
    })
    .join('\n');

  const dailySummary = Object.entries(daily)
    .sort(([a], [b]) => b.localeCompare(a))
    .slice(0, 14)
    .map(([date, data]) => `  ${date}: ${data.orders || 0} orders, Revenue: ₱${money(data.revenue)}, AOV: ₱${money(data.averageOrderValue)}`)
    .join('\n');

  const latestDay = Object.keys(daily).sort((a, b) => b.localeCompare(a))[0];
  let hourlySummary = 'No hourly data available.';
  if (latestDay && hourly[latestDay]) {
    const hourlyRows = Object.entries(hourly[latestDay])
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([hour, data]) => `  ${hour}:00 - ${data.orders || 0} orders, Revenue: ₱${money(data.revenue)}`)
      .join('\n');
    hourlySummary = `Hourly data for ${latestDay}:\n${hourlyRows}`;
  }

  // Compact multi-day activity map so the AI can infer operating hours,
  // busy/slow periods and recurring intraday behavior — not just today.
  const recentHourlyDays = Object.keys(hourly).sort((a, b) => b.localeCompare(a)).slice(0, 7).reverse();
  const activitySummary = recentHourlyDays
    .map((day) => {
      const hours = Object.entries(hourly[day] || {})
        .filter(([, d]) => Number(d.orders || 0) > 0)
        .sort(([a], [b]) => a.localeCompare(b));
      if (hours.length === 0) return `  ${day}: no recorded activity`;
      const first = hours[0][0];
      const last = hours[hours.length - 1][0];
      const busiest = [...hours].sort(([, a], [, b]) => Number(b.orders || 0) - Number(a.orders || 0))[0];
      return `  ${day}: active ${first}:00–${last}:59, busiest ${busiest[0]}:00 (${busiest[1].orders} orders, ₱${money(busiest[1].revenue)})`;
    })
    .join('\n');

  // Weekday averages — weekly cycle evidence.
  const weekdayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const byDow = Array.from({ length: 7 }, () => []);
  Object.entries(daily).forEach(([key, d]) => {
    const rev = Number(d.revenue || 0);
    if (rev > 0) {
      const date = new Date(`${key}T00:00:00`);
      if (!Number.isNaN(date.getTime())) byDow[date.getDay()].push(rev);
    }
  });
  const weekdaySummary = byDow
    .map((list, i) => (list.length > 0
      ? `  ${weekdayNames[i]}: avg ₱${money(list.reduce((s, v) => s + v, 0) / list.length)} over ${list.length} day(s)`
      : null))
    .filter(Boolean)
    .join('\n');

  const patternsSummary = (detectedPatterns || [])
    .map((p) => `  - [${p.tag}, confidence ${p.confidence}%] ${p.text}`)
    .join('\n');

  const weeklySummary = Object.entries(weekly)
    .sort(([a], [b]) => b.localeCompare(a))
    .slice(0, 8)
    .map(([week, data]) => `  ${week}: ${data.orders || 0} orders, Revenue: ₱${money(data.revenue)}`)
    .join('\n');

  const monthlySummary = Object.entries(monthly)
    .sort(([a], [b]) => b.localeCompare(a))
    .slice(0, 6)
    .map(([month, data]) => `  ${month}: ${data.orders || 0} orders, Revenue: ₱${money(data.revenue)}`)
    .join('\n');

  const requestedMode = mode === 'executive'
    ? 'executive business analysis presentation'
    : mode === 'deep'
    ? 'deep analysis report'
    : mode === 'live'
      ? 'AI live operations feed hourly update'
      : mode === 'briefing'
        ? 'AI shift handoff'
        : mode === 'leak'
          ? 'AI revenue leak detector'
          : mode === 'simulation'
            ? 'AI decision simulator'
            : mode === 'opschat'
              ? 'AI operations manager work chat'
              : 'real-time quick insight';

  return `Here is the complete analytics data from our restaurant self-ordering system.

Requested analysis mode: ${requestedMode}
Report time: ${reportContext.asOfLabel || 'Current time'}
Manager name: ${reportContext.managerNickname || 'Manager'}
Branch: ${reportContext.branchLabel || 'Current branch'}
Time of day label: ${reportContext.timeOfDayLabel || 'Current shift'}
Manager question or scenario: ${reportContext.scenario || 'N/A'}

=== OVERALL SUMMARY ===
Total Orders: ${summary.totalOrders || 0}
Total Revenue: ₱${money(summary.totalRevenue)}
Average Order Value: ₱${money(summary.averageOrderValue)}
Best Selling Item: ${formatProductName(summary.bestSellingItem || 'N/A')}
Least Selling Item: ${formatProductName(summary.leastSellingItem || 'N/A')}
Last Updated: ${summary.lastUpdated || 'N/A'}

=== CURRENT PERIOD ===
Today: ${todayAnalytics.orders || 0} orders, Revenue: ₱${money(todayAnalytics.revenue)}
This Week: ${weekAnalytics.orders || 0} orders, Revenue: ₱${money(weekAnalytics.revenue)}
This Month: ${monthAnalytics.orders || 0} orders, Revenue: ₱${money(monthAnalytics.revenue)}

=== AVERAGES ===
Mean Daily Orders: ${statistics.ordersPerDay?.mean || 0}
Median Daily Orders: ${statistics.ordersPerDay?.median || 0}
Mean Daily Revenue: ₱${money(statistics.revenuePerDay?.mean)}
Median Daily Revenue: ₱${money(statistics.revenuePerDay?.median)}

=== PRODUCTS (${productEntries.length} items) ===
${productSummary || 'No product data available.'}

=== INVENTORY (${Object.keys(inventory).length} items) ===
${inventorySummary || 'No inventory data available.'}

=== DAILY TRENDS (Last 14 days) ===
${dailySummary || 'No daily data available.'}

=== HOURLY DISTRIBUTION ===
${hourlySummary}

=== DAILY ACTIVITY MAP (Last 7 recorded days) ===
${activitySummary || 'No hourly history available.'}

=== WEEKDAY AVERAGES ===
${weekdaySummary || 'Not enough history for weekday averages.'}

=== DETECTED OPERATIONAL PATTERNS (pre-computed, statistically verified) ===
${patternsSummary || 'No strong patterns detected yet — more history needed.'}

=== WEEKLY TRENDS ===
${weeklySummary || 'No weekly data available.'}

=== MONTHLY TRENDS ===
${monthlySummary || 'No monthly data available.'}

Please provide operational interpretation, not a dashboard recap.`;
}

export function parseModelJson(raw) {
  const cleaned = String(raw || '')
    .replace(/```json\n?/g, '')
    .replace(/```\n?/g, '')
    .trim();

  return JSON.parse(cleaned);
}
