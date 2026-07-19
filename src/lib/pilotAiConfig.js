/**
 * AI request configuration for the pilot.
 *
 * SECURITY: the OpenAI API key is NO LONGER present in the client. All AI requests now go to a
 * same-origin, authenticated server proxy (a Firebase Function mounted at /api/ai via a Hosting
 * rewrite) which holds the key server-side. Nothing secret ships to the browser bundle.
 *
 * Override VITE_AI_PROXY_URL only if the proxy lives on a different origin (e.g. a Railway
 * backend); the default is the same-origin path so there is no CORS and no key exposure.
 */

const PROXY_BASE = import.meta.env.VITE_AI_PROXY_URL || '/api/ai';

export const pilotAiConfig = {
  model: 'gpt-4o-mini',
  endpoint: `${PROXY_BASE}/chat/completions`,
};
