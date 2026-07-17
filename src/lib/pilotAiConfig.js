/**
 * Centralized OpenAI configuration for the pilot.
 *
 * TEMPORARY: For the pilot, the API key is loaded from a Vite environment
 * variable (VITE_OPENAI_API_KEY in .env.local). When the project transitions
 * to production, replace this with a backend service call.
 */

const OPENAI_API_KEY = import.meta.env.VITE_OPENAI_API_KEY || '';

export const pilotAiConfig = {
  apiKey: OPENAI_API_KEY,
  model: 'gpt-4o-mini',
  endpoint: 'https://api.openai.com/v1/chat/completions',
};
