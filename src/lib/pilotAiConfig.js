/**
 * AI request configuration for the client.
 *
 * SECURITY + ARCHITECTURE: the OpenAI API key is NOT in the client. All AI requests go to the
 * FastAPI backend on Railway — the single Backend-for-Frontend (BFF) and the only holder of the
 * key (ADR-17). There are no Firebase Cloud Functions, Cloud Run, or serverless AI paths.
 *
 * VITE_API_BASE_URL is the Railway backend origin (e.g. https://touchorders-api.up.railway.app).
 * Leave it empty for local dev behind a Vite proxy. The client sends the Firebase App Check token
 * and the signed-in user's ID token (via fetchWithAppCheck); FastAPI verifies both server-side.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export const pilotAiConfig = {
  model: 'gpt-4o-mini',
  endpoint: `${API_BASE}/api/ai/chat/completions`,
};
