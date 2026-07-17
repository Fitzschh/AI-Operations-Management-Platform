/**
 * Live Analyst Provider — Session-Level Background AI Service
 *
 * Manages the entire Live Operations Analyst lifecycle at the app level.
 * This provider lives above the router so it is NEVER unmounted by navigation.
 *
 * Lifecycle:
 *   1. Login → Dashboard loads → AI Shift Handoff auto-triggers
 *   2. 15 seconds after handoff → first Live Operations Analysis
 *   3. Random 4–10 min interval → re-surface latest analysis notification
 *   4. Hourly boundary → fresh analysis replaces the previous one
 *   5. Logout → destroy everything
 *
 * Page navigation has ZERO effect on this provider.
 */

import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from 'react';
import { useAuth } from './AuthContext';
import { getUserBranch, isUserAdmin, AUTH_CONFIG } from '../config/authConfig';
import { formatDateKey } from '../lib/analyticsApi';
import { generateAIAnalysis, clearAnalysisCache } from '../lib/aiAnalystService';

// ─── Constants ──────────────────────────────────────────────────────────────

const MIN_NOTIFICATION_INTERVAL_MS = 4 * 60 * 1000;   // 4 minutes
const MAX_NOTIFICATION_INTERVAL_MS = 10 * 60 * 1000;  // 10 minutes
const INITIAL_ANALYSIS_DELAY_MS = 15 * 1000;           // 15s after handoff
const NOTIFICATION_DISPLAY_MS = 15000;                 // 15s visible
const PREPARING_MIN_DISPLAY_MS = 3000;                 // minimum preparing state

// Session keys (shared with AuthContext which clears them on logout)
const SK_HANDOFF_DONE = 'shiftHandoffCompleted';
const SK_INITIAL_DONE = 'liveOpsInitialRunCompleted';
const SK_FEED_ITEMS = 'aiFeedItems';

// ─── Context ────────────────────────────────────────────────────────────────

const LiveAnalystContext = createContext(null);

// ─── State Reducer ──────────────────────────────────────────────────────────

const A = {
  ADD_FEED_ITEM: 'ADD_FEED_ITEM',
  SET_PREPARING: 'SET_PREPARING',
  SET_GENERATING: 'SET_GENERATING',
  SET_ERROR: 'SET_ERROR',
  SET_HANDOFF_COMPLETE: 'SET_HANDOFF_COMPLETE',
  SET_NOTIFICATION_OPEN: 'SET_NOTIFICATION_OPEN',
  RESET: 'RESET',
};

function createInitialState() {
  // Restore persisted feed items from the current session
  let feedItems = [];
  try {
    const saved = sessionStorage.getItem(SK_FEED_ITEMS);
    if (saved) feedItems = JSON.parse(saved) || [];
  } catch { /* ignore */ }

  return {
    feedItems,
    preparingBriefing: null,
    generating: false,
    error: null,
    handoffComplete: sessionStorage.getItem(SK_HANDOFF_DONE) === '1',
    notificationOpen: false,
  };
}

function reducer(state, action) {
  switch (action.type) {
    case A.ADD_FEED_ITEM: {
      const item = action.payload;
      const key = item.mode || 'default';
      // Replace same-mode items, drop preparing states
      const filtered = state.feedItems.filter(
        (f) => f.mode !== 'briefing-preparing' && (f.mode || 'default') !== key
      );
      const next = [...filtered, item].slice(-12);
      // Persist to sessionStorage
      try { sessionStorage.setItem(SK_FEED_ITEMS, JSON.stringify(next)); } catch { /* */ }
      return { ...state, feedItems: next };
    }
    case A.SET_PREPARING:
      return { ...state, preparingBriefing: action.payload };
    case A.SET_GENERATING:
      return { ...state, generating: action.payload };
    case A.SET_ERROR:
      return { ...state, error: action.payload };
    case A.SET_HANDOFF_COMPLETE:
      return { ...state, handoffComplete: action.payload };
    case A.SET_NOTIFICATION_OPEN:
      return { ...state, notificationOpen: action.payload };
    case A.RESET: {
      try {
        sessionStorage.removeItem(SK_FEED_ITEMS);
      } catch { /* */ }
      return { ...createInitialState(), feedItems: [], handoffComplete: false };
    }
    default:
      return state;
  }
}

// ─── Utilities ──────────────────────────────────────────────────────────────

function getRandomInterval() {
  return Math.floor(
    Math.random() * (MAX_NOTIFICATION_INTERVAL_MS - MIN_NOTIFICATION_INTERVAL_MS) +
      MIN_NOTIFICATION_INTERVAL_MS
  );
}

function getMsUntilNextHour() {
  const now = new Date();
  const next = new Date(now);
  next.setHours(now.getHours() + 1, 0, 0, 0);
  return next.getTime() - now.getTime();
}

function timeOfDayLabel() {
  const h = new Date().getHours();
  if (h >= 5 && h < 11) return 'Morning';
  if (h >= 11 && h < 13) return 'Noon';
  if (h >= 13 && h < 18) return 'Afternoon';
  return 'Evening';
}

function formatBranchLabel(branchId) {
  const cfg = AUTH_CONFIG.branches?.[branchId];
  if (cfg?.name) return cfg.name;
  const match = String(branchId || '').match(/^branch(\d+)$/i);
  if (match) return `Branch ${match[1]}`;
  return String(branchId || 'this branch')
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ─── Provider ───────────────────────────────────────────────────────────────

export function LiveAnalystProvider({ children }) {
  const { user, isAuthenticated, nicknameLoaded, nickname } = useAuth();
  const [state, dispatch] = useReducer(reducer, null, createInitialState);

  // ── Refs (survive re-renders, never cause re-triggers) ────────────
  const generatingRef = useRef(false);
  const handoffInFlightRef = useRef(false);
  const liveInFlightRef = useRef(false);
  const handoffStartedRef = useRef(false);
  const preparingVisibleUntilRef = useRef(0);
  const notificationTimerRef = useRef(null);
  const randomTimerRef = useRef(null);
  const hourlyTimerRef = useRef(null);
  const mountedRef = useRef(true);

  // We need analytics data from BranchDataContext, but LiveAnalystProvider
  // sits above the router. We use a ref that gets populated via a setter
  // that BranchDataContext (or the AppShell) calls.
  const branchDataRef = useRef(null);
  const [branchDataVersion, setBranchDataVersion] = useReducer((x) => x + 1, 0);

  // ── Determine active branch ──────────────────────────────────────
  const activeBranch = useMemo(() => {
    if (!user?.email) return null;
    if (isUserAdmin(user.email)) return 'branch1';
    return getUserBranch(user.email) || null;
  }, [user?.email]);

  const branchLabel = useMemo(() => formatBranchLabel(activeBranch), [activeBranch]);

  // ── Cleanup on unmount ───────────────────────────────────────────
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clearTimeout(notificationTimerRef.current);
      clearTimeout(randomTimerRef.current);
      clearTimeout(hourlyTimerRef.current);
    };
  }, []);

  // ── Reset on logout ──────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) {
      dispatch({ type: A.RESET });
      clearTimeout(notificationTimerRef.current);
      clearTimeout(randomTimerRef.current);
      clearTimeout(hourlyTimerRef.current);
      generatingRef.current = false;
      handoffInFlightRef.current = false;
      liveInFlightRef.current = false;
      handoffStartedRef.current = false;
      branchDataRef.current = null;
    }
  }, [isAuthenticated]);

  // ── Notification show / hide ─────────────────────────────────────
  const showNotification = useCallback((durationMs = NOTIFICATION_DISPLAY_MS) => {
    dispatch({ type: A.SET_NOTIFICATION_OPEN, payload: true });
    clearTimeout(notificationTimerRef.current);
    if (durationMs !== null) {
      notificationTimerRef.current = setTimeout(() => {
        if (mountedRef.current) {
          dispatch({ type: A.SET_NOTIFICATION_OPEN, payload: false });
        }
      }, durationMs);
    }
  }, []);

  // ── Setter for branch data (called by AppShell/DashboardPage) ────
  const setBranchData = useCallback((data) => {
    branchDataRef.current = data;
    setBranchDataVersion();
  }, []);

  // ── Core generation function ─────────────────────────────────────
  const handleGenerate = useCallback(
    async (mode = 'realtime', forceRefresh = false, reportContext = null, revealNotification = true) => {
      const bd = branchDataRef.current;
      if (generatingRef.current || !activeBranch || !bd?.aiAnalyticsData) return null;
      generatingRef.current = true;
      dispatch({ type: A.SET_GENERATING, payload: true });
      dispatch({ type: A.SET_ERROR, payload: null });

      try {
        if (forceRefresh) {
          clearAnalysisCache(activeBranch, mode);
        }
        const payload = reportContext
          ? { ...bd.aiAnalyticsData, reportContext }
          : bd.aiAnalyticsData;

        const result = await generateAIAnalysis(payload, activeBranch, forceRefresh, mode);

        if (mode === 'briefing') {
          const remaining = preparingVisibleUntilRef.current - Date.now();
          if (remaining > 0) await new Promise((r) => setTimeout(r, remaining));
          dispatch({ type: A.SET_PREPARING, payload: null });
        }

        dispatch({ type: A.ADD_FEED_ITEM, payload: result });

        if (revealNotification && mountedRef.current) {
          showNotification();
        }
        return result;
      } catch (err) {
        console.error('[LiveAnalyst] Generation failed:', err);
        if (mode === 'briefing') {
          const remaining = preparingVisibleUntilRef.current - Date.now();
          if (remaining > 0) await new Promise((r) => setTimeout(r, remaining));
          dispatch({ type: A.SET_PREPARING, payload: null });
        }
        dispatch({ type: A.SET_ERROR, payload: err.message || 'Analysis failed.' });
        if (revealNotification && mountedRef.current) {
          showNotification();
        }
        return null;
      } finally {
        generatingRef.current = false;
        if (mountedRef.current) {
          dispatch({ type: A.SET_GENERATING, payload: false });
        }
      }
    },
    [activeBranch, showNotification]
  );

  // ── AI Shift Handoff (auto on login) ─────────────────────────────
  const generateShiftHandoff = useCallback(async () => {
    if (!activeBranch || handoffInFlightRef.current) return;
    const bd = branchDataRef.current;
    if (!bd?.hasOrders) return;

    // Already done this session?
    if (sessionStorage.getItem(SK_HANDOFF_DONE) === '1') {
      dispatch({ type: A.SET_HANDOFF_COMPLETE, payload: true });
      return;
    }

    handoffInFlightRef.current = true;
    try {
      const result = await handleGenerate('briefing', true, {
        asOfLabel: 'AI Shift Handoff',
        branchLabel,
        managerNickname: nickname?.trim() || 'Manager',
        timeOfDayLabel: timeOfDayLabel(),
        generatedFor: new Date().toISOString(),
      });
      if (result) {
        sessionStorage.setItem(SK_HANDOFF_DONE, '1');
        console.log('[LiveAnalyst] Shift handoff complete');
      }
    } finally {
      handoffInFlightRef.current = false;
      if (mountedRef.current) {
        dispatch({ type: A.SET_HANDOFF_COMPLETE, payload: true });
      }
    }
  }, [activeBranch, branchLabel, handleGenerate, nickname]);

  // ── Live Operations Report ───────────────────────────────────────
  const generateLiveReport = useCallback(async () => {
    const bd = branchDataRef.current;
    if (!activeBranch || !bd?.hasOrders || liveInFlightRef.current) return;

    liveInFlightRef.current = true;
    try {
      const now = new Date();
      const result = await handleGenerate('live', true, {
        asOfLabel: now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }),
        scheduledHour: now.getHours(),
        generatedFor: now.toISOString(),
      });
      if (result) {
        console.log('[LiveAnalyst] Live analysis generated');
      }
    } finally {
      liveInFlightRef.current = false;
    }
  }, [activeBranch, handleGenerate]);

  // ── Trigger: Shift Handoff on login ──────────────────────────────
  useEffect(() => {
    if (!isAuthenticated || !activeBranch || !nicknameLoaded) return;
    const bd = branchDataRef.current;
    if (!bd?.hasOrders) return;
    if (handoffStartedRef.current) return;
    if (sessionStorage.getItem(SK_HANDOFF_DONE) === '1') {
      dispatch({ type: A.SET_HANDOFF_COMPLETE, payload: true });
      return;
    }

    handoffStartedRef.current = true;

    // Show preparing state immediately
    preparingVisibleUntilRef.current = Date.now() + PREPARING_MIN_DISPLAY_MS;
    dispatch({
      type: A.SET_PREPARING,
      payload: {
        mode: 'briefing-preparing',
        generatedAt: new Date().toISOString(),
        greeting: `Good ${timeOfDayLabel()}, ${nickname?.trim() || 'Manager'}.`,
        branchWelcome: `Welcome to ${branchLabel}.`,
        message: 'I am preparing your AI Shift Handoff from the latest branch data.',
      },
    });
    dispatch({ type: A.SET_ERROR, payload: null });
    showNotification(null); // Keep open until handoff completes

    generateShiftHandoff();
  }, [isAuthenticated, activeBranch, nicknameLoaded, branchDataVersion, nickname, branchLabel, showNotification, generateShiftHandoff]);

  // ── Trigger: Initial live analysis (15s after handoff) ───────────
  useEffect(() => {
    if (!state.handoffComplete || !activeBranch) return;
    if (sessionStorage.getItem(SK_INITIAL_DONE) === '1') return;
    const bd = branchDataRef.current;
    if (!bd?.hasOrders) return;

    const timer = setTimeout(async () => {
      if (!mountedRef.current) return;
      sessionStorage.setItem(SK_INITIAL_DONE, '1');
      await generateLiveReport();
    }, INITIAL_ANALYSIS_DELAY_MS);

    return () => clearTimeout(timer);
  }, [state.handoffComplete, activeBranch, branchDataVersion, generateLiveReport]);

  // ── Trigger: Random notification resurface (4–10 min cycle) ──────
  useEffect(() => {
    if (!state.handoffComplete || !activeBranch) return;
    const bd = branchDataRef.current;
    if (!bd?.hasOrders) return;

    function scheduleNext() {
      const ms = getRandomInterval();
      console.log(`[LiveAnalyst] Notification resurface in ${Math.round(ms / 1000)}s`);
      randomTimerRef.current = setTimeout(() => {
        if (!mountedRef.current) return;
        // Re-show the latest analysis (no new API call)
        if (state.feedItems.length > 0) {
          showNotification();
        }
        scheduleNext();
      }, ms);
    }

    // Start the random cycle after handoff is complete + initial analysis delay
    const startDelay = sessionStorage.getItem(SK_INITIAL_DONE) === '1'
      ? getRandomInterval()
      : INITIAL_ANALYSIS_DELAY_MS + 5000; // Wait for initial to finish first

    randomTimerRef.current = setTimeout(() => {
      if (!mountedRef.current) return;
      if (state.feedItems.length > 0) {
        showNotification();
      }
      scheduleNext();
    }, startDelay);

    return () => clearTimeout(randomTimerRef.current);
  }, [state.handoffComplete, activeBranch, branchDataVersion, showNotification, state.feedItems.length]);

  // ── Trigger: Hourly analysis cycle ───────────────────────────────
  useEffect(() => {
    if (!state.handoffComplete || !activeBranch) return;
    const bd = branchDataRef.current;
    if (!bd?.hasOrders) return;

    function scheduleHourly() {
      const ms = getMsUntilNextHour();
      console.log(`[LiveAnalyst] Hourly cycle in ${Math.round(ms / 60000)} minutes`);
      hourlyTimerRef.current = setTimeout(async () => {
        if (!mountedRef.current) return;
        console.log('[LiveAnalyst] Hourly cycle triggered');
        clearAnalysisCache(activeBranch, 'live');
        await generateLiveReport();
        if (mountedRef.current) {
          scheduleHourly();
        }
      }, ms);
    }

    scheduleHourly();

    return () => clearTimeout(hourlyTimerRef.current);
  }, [state.handoffComplete, activeBranch, branchDataVersion, generateLiveReport]);

  // ── Context value ────────────────────────────────────────────────
  const latestFeedItem = state.feedItems[state.feedItems.length - 1] || null;
  const analysis = state.preparingBriefing || latestFeedItem;

  const contextValue = useMemo(
    () => ({
      // State
      feedItems: state.feedItems,
      latestAnalysis: analysis,
      preparingBriefing: state.preparingBriefing,
      generating: state.generating,
      error: state.error,
      handoffComplete: state.handoffComplete,
      notificationOpen: state.notificationOpen,
      activeBranch,
      hasData: !!branchDataRef.current?.hasOrders,

      // Actions
      showNotification,
      setNotificationOpen: (open) =>
        dispatch({ type: A.SET_NOTIFICATION_OPEN, payload: open }),
      setBranchData,
      generateLiveReport,
    }),
    [
      state,
      analysis,
      activeBranch,
      showNotification,
      setBranchData,
      generateLiveReport,
    ]
  );

  return (
    <LiveAnalystContext.Provider value={contextValue}>
      {children}
    </LiveAnalystContext.Provider>
  );
}

// ─── Hook ───────────────────────────────────────────────────────────────────

export function useLiveAnalyst() {
  const ctx = useContext(LiveAnalystContext);
  if (!ctx) {
    throw new Error('useLiveAnalyst must be used within a LiveAnalystProvider.');
  }
  return ctx;
}

export default LiveAnalystContext;
