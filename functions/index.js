/**
 * Server-side OpenAI proxy (Firebase Functions v2).
 *
 * Purpose: keep the OpenAI API key OFF the client. The browser calls this same-origin endpoint
 * (mounted at /api/ai via a Hosting rewrite); this function holds the key as a server secret and
 * forwards the request to OpenAI. The key is never in the client bundle, so it cannot leak and be
 * auto-revoked.
 *
 * Abuse protection (so this is not an open, credit-draining relay):
 *   - Requires a valid Firebase ID token (only signed-in app users can call it).
 *   - Verifies the Firebase App Check token when present (anti-bot).
 *   - Enforces a model allowlist and a hard output-token cap.
 *
 * Deploy:
 *   firebase functions:secrets:set OPENAI_API_KEY   # paste the key once, stored server-side
 *   firebase deploy --only functions,hosting
 */

const { onRequest } = require("firebase-functions/v2/https");
const { defineSecret } = require("firebase-functions/params");
const logger = require("firebase-functions/logger");
const admin = require("firebase-admin");

admin.initializeApp();

const OPENAI_API_KEY = defineSecret("OPENAI_API_KEY");

const ALLOWED_MODELS = new Set(["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"]);
const MAX_OUTPUT_TOKENS = 3000;
const OPENAI_URL = "https://api.openai.com/v1/chat/completions";

exports.openaiProxy = onRequest(
  { secrets: [OPENAI_API_KEY], region: "us-central1", cors: false, timeoutSeconds: 60 },
  async (req, res) => {
    if (req.method !== "POST") {
      res.status(405).json({ error: { message: "Method not allowed" } });
      return;
    }

    // Anti-bot: verify App Check when the client supplied a token.
    const appCheckToken = req.header("X-Firebase-AppCheck");
    if (appCheckToken) {
      try {
        await admin.appCheck().verifyToken(appCheckToken);
      } catch (err) {
        logger.warn("App Check verification failed", { message: err.message });
        res.status(401).json({ error: { message: "App Check verification failed" } });
        return;
      }
    }

    // Hard gate: only a signed-in user may use the proxy. fetchWithAppCheck sends the ID token as
    // the ?auth= query param (Firebase REST convention); also accept a Bearer header.
    const idToken =
      (req.query.auth && String(req.query.auth)) ||
      (req.header("Authorization") || "").replace(/^Bearer\s+/i, "");
    try {
      if (!idToken) throw new Error("missing id token");
      await admin.auth().verifyIdToken(idToken);
    } catch (err) {
      res.status(401).json({ error: { message: "Unauthorized: sign-in required" } });
      return;
    }

    const body = req.body || {};
    if (!Array.isArray(body.messages) || body.messages.length === 0) {
      res.status(400).json({ error: { message: "messages[] is required" } });
      return;
    }

    const payload = {
      model: ALLOWED_MODELS.has(body.model) ? body.model : "gpt-4o-mini",
      messages: body.messages,
      response_format: body.response_format,
      temperature: typeof body.temperature === "number" ? body.temperature : 0.35,
      max_tokens: Math.min(Number(body.max_tokens) || 350, MAX_OUTPUT_TOKENS),
    };

    try {
      const upstream = await fetch(OPENAI_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${OPENAI_API_KEY.value()}`,
        },
        body: JSON.stringify(payload),
      });
      const data = await upstream.json().catch(() => ({}));
      // Pass OpenAI's status through so the client's existing error handling still works.
      res.status(upstream.status).json(data);
    } catch (err) {
      logger.error("OpenAI upstream error", { message: err.message });
      res.status(502).json({ error: { message: "Upstream error contacting OpenAI" } });
    }
  }
);
