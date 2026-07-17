import { database } from './firebase';
import { ref, push, set, get, query, orderByChild, limitToLast } from 'firebase/database';

/**
 * Save a shift handoff analysis to Firebase RTDB.
 */
export async function saveShiftHandoff(branchId, handoffData) {
  if (!branchId || !handoffData) return null;

  const handoffsRef = ref(database, `${branchId}/shiftHandoffs`);
  const newRef = push(handoffsRef);

  const record = {
    ...handoffData,
    savedAt: new Date().toISOString(),
    id: newRef.key,
  };

  await set(newRef, record);
  return record;
}

/**
 * Fetch recent shift handoffs from Firebase RTDB.
 */
export async function getShiftHandoffs(branchId, limit = 50) {
  if (!branchId) return [];

  const handoffsRef = ref(database, `${branchId}/shiftHandoffs`);
  const q = query(handoffsRef, orderByChild('savedAt'), limitToLast(limit));

  const snapshot = await get(q);
  if (!snapshot.exists()) return [];

  const items = [];
  snapshot.forEach((child) => {
    items.push({ id: child.key, ...child.val() });
  });

  return items.reverse();
}

/**
 * Save an hourly AI analysis to Firebase RTDB.
 */
export async function saveHourlyAnalysis(branchId, analysisData) {
  if (!branchId || !analysisData) return null;

  const analysesRef = ref(database, `${branchId}/hourlyAnalyses`);
  const newRef = push(analysesRef);

  const severity = determineSeverity(analysisData);

  const record = {
    ...analysisData,
    severity,
    savedAt: new Date().toISOString(),
    id: newRef.key,
  };

  await set(newRef, record);
  return record;
}

/**
 * Fetch recent hourly analyses from Firebase RTDB.
 */
export async function getHourlyAnalyses(branchId, limit = 100) {
  if (!branchId) return [];

  const analysesRef = ref(database, `${branchId}/hourlyAnalyses`);
  const q = query(analysesRef, orderByChild('savedAt'), limitToLast(limit));

  const snapshot = await get(q);
  if (!snapshot.exists()) return [];

  const items = [];
  snapshot.forEach((child) => {
    items.push({ id: child.key, ...child.val() });
  });

  return items.reverse();
}

/**
 * Determine severity from AI analysis result.
 * Returns 'red', 'yellow', or 'green'.
 */
function determineSeverity(analysis) {
  if (!analysis) return 'green';

  const priority = analysis.insight?.priority || '';
  if (priority === 'HIGH') return 'red';
  if (priority === 'MEDIUM') return 'yellow';

  const text = JSON.stringify(analysis).toLowerCase();
  const urgentTerms = ['urgent', 'critical', 'stockout', 'out of stock', 'immediately'];
  const warningTerms = ['low stock', 'declining', 'below', 'warning', 'attention'];

  if (urgentTerms.some((term) => text.includes(term))) return 'red';
  if (warningTerms.some((term) => text.includes(term))) return 'yellow';

  return 'green';
}
