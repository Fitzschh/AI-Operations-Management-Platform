import { initializeApp } from 'firebase/app';
import { initializeAppCheck, ReCaptchaV3Provider, getToken } from 'firebase/app-check';
import { getAuth } from 'firebase/auth';
import { getDatabase } from 'firebase/database';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const firebaseApp = initializeApp(firebaseConfig);
export const auth = getAuth(firebaseApp);
export const database = getDatabase(firebaseApp);

let appCheckInstance = null;
try {
  const siteKey = import.meta.env.VITE_RECAPTCHA_SITE_KEY;
  if (siteKey) {
    appCheckInstance = initializeAppCheck(firebaseApp, {
      provider: new ReCaptchaV3Provider(siteKey),
      isTokenAutoRefreshEnabled: true,
    });
  }
} catch (err) {
  console.warn('App Check init failed:', err);
}

const databaseURL = firebaseConfig.databaseURL;

export async function fetchWithAppCheck(url, options = {}) {
  // 1. Get App Check Token
  let appCheckToken = null;
  if (appCheckInstance) {
    try {
      const tokenResult = await getToken(appCheckInstance);
      if (tokenResult?.token) appCheckToken = tokenResult.token;
    } catch (e) {
      console.warn('App Check token failed:', e);
    }
  }

  // 2. Get Auth Token
  let authToken = null;
  try {
    if (auth.currentUser) {
      authToken = await auth.currentUser.getIdToken();
    }
  } catch (e) {
    // This might happen if user just logged out or token expired
    console.warn('Auth token retrieval failed:', e);
  }

  const headers = new Headers(options.headers || {});
  if (appCheckToken) headers.set('X-Firebase-AppCheck', appCheckToken);

  // 3. Append Auth Token to URL for Firebase REST API
  let finalUrl = url;
  if (authToken) {
    const separator = finalUrl.includes('?') ? '&' : '?';
    finalUrl = `${finalUrl}${separator}auth=${authToken}`;
  }

  return fetch(finalUrl, { ...options, headers });
}

export function dbUrl(path) {
  const clean = path.startsWith('/') ? path.slice(1) : path;
  const encoded = clean.split('/').map(seg => encodeURIComponent(seg)).join('/');
  return `${databaseURL}/${encoded}.json`;
}
