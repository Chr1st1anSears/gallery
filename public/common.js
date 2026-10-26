// common.js — shared helpers for every Gallery page.
//
// Security notes:
//   * All user-controlled data (names, dates, descriptions, relationship text)
//     is rendered with textContent via `el()`. Never use innerHTML with data.
//   * Editor status comes from the Firebase Auth custom claim `editor`. The UI
//     uses it only to show/hide controls; the Cloud Functions and Storage rules
//     enforce it server-side.

(function () {
  'use strict';

  // Longest edge (px) for scan images sent to the backend. The embedding model
  // works at low resolution anyway, so this makes scans faster and cheaper.
  const SCAN_MAX_EDGE = 1024;
  const SCAN_JPEG_QUALITY = 0.85;

  /**
   * Creates a DOM element safely.
   *   el('a', { href: '/x', className: 'btn' }, ['text', childNode])
   * Strings in `children` become text nodes (never parsed as HTML).
   */
  function el(tag, props, children) {
    const node = document.createElement(tag);
    if (props) {
      for (const [key, value] of Object.entries(props)) {
        if (value === undefined || value === null) continue;
        if (key === 'className') node.className = value;
        else if (key === 'text') node.textContent = value;
        else if (key === 'dataset') Object.assign(node.dataset, value);
        else if (key === 'style') Object.assign(node.style, value);
        else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
        else node.setAttribute(key, value);
      }
    }
    for (const child of [].concat(children || [])) {
      if (child === null || child === undefined || child === false) continue;
      node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
    }
    return node;
  }

  /** Builds a same-origin URL to the photo page, encoding the ID safely. */
  function photoUrl(id) {
    return '/view-photo.html?id=' + encodeURIComponent(id);
  }

  /** Only allow https image URLs from Firebase Storage to be used as <img src>. */
  function safeImageUrl(url) {
    try {
      const u = new URL(url);
      return u.protocol === 'https:' && u.hostname === 'firebasestorage.googleapis.com' ? u.href : '';
    } catch (_) {
      return '';
    }
  }

  /** Returns true if the signed-in user has the `editor` custom claim. */
  async function isEditor(user, forceRefresh) {
    if (!user) return false;
    try {
      const token = await user.getIdTokenResult(!!forceRefresh);
      return token.claims.editor === true;
    } catch (_) {
      return false;
    }
  }

  /** Friendly message for a callable-function error (no internals). */
  function errorMessage(error) {
    const known = ['permission-denied', 'unauthenticated', 'invalid-argument', 'not-found'];
    const code = (error && error.code || '').replace('functions/', '');
    if (known.includes(code) && error.message) return error.message;
    return 'Something went wrong. Please try again.';
  }

  /**
   * Wires up the navbar Login / Logout / user-name elements if present.
   * Calls onChange(user, editor) whenever auth state changes.
   */
  function initAuthNav(onChange) {
    const auth = firebase.auth();
    const loginContainer = document.getElementById('login-container');
    const loginButton = document.getElementById('login-button');
    const logoutButton = document.getElementById('logout-button');
    const userInfo = document.getElementById('user-info');
    const userName = document.getElementById('user-name');

    if (loginButton) {
      loginButton.addEventListener('click', (e) => {
        e.preventDefault();
        auth.signInWithPopup(new firebase.auth.GoogleAuthProvider())
          .catch(() => console.error('Sign-in failed or was cancelled.'));
      });
    }
    if (logoutButton) {
      logoutButton.addEventListener('click', (e) => {
        e.preventDefault();
        // Full reload after sign-out clears any in-memory state.
        auth.signOut().finally(() => window.location.reload());
      });
    }

    auth.onAuthStateChanged(async (user) => {
      if (userInfo && loginContainer && userName) {
        userName.textContent = user ? (user.displayName || user.email || '') : '';
        userInfo.style.display = user ? 'block' : 'none';
        loginContainer.style.display = user ? 'none' : 'block';
      }
      // Force-refresh once on sign-in so newly granted claims take effect.
      const editor = await isEditor(user, true);
      if (onChange) onChange(user, editor);
    });
  }

  /** Downscales an image File to a JPEG and returns base64 (no data: prefix). */
  function fileToScaledBase64(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        const scale = Math.min(1, SCAN_MAX_EDGE / Math.max(img.naturalWidth, img.naturalHeight));
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(img.naturalWidth * scale);
        canvas.height = Math.round(img.naturalHeight * scale);
        canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);
        resolve(canvas.toDataURL('image/jpeg', SCAN_JPEG_QUALITY).split(',')[1]);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error('Could not read that image.'));
      };
      img.src = url;
    });
  }

  /**
   * Wires up a "Scan" button + hidden camera <input> + status element.
   * On a match, navigates to the photo's page.
   */
  function initScan({ buttonId = 'scan-photo-button', inputId = 'camera-input', statusId = 'status-message' } = {}) {
    const scanButton = document.getElementById(buttonId);
    const cameraInput = document.getElementById(inputId);
    const statusMessage = document.getElementById(statusId);
    if (!scanButton || !cameraInput || !statusMessage) return;

    const findPhotoByMatch = firebase.functions().httpsCallable('findphotobymatch');
    const setBusy = (busy) => {
      scanButton.disabled = busy;
      scanButton.setAttribute('aria-disabled', String(busy));
    };

    scanButton.addEventListener('click', (e) => {
      e.preventDefault();
      cameraInput.click();
    });

    cameraInput.addEventListener('change', async () => {
      const file = cameraInput.files && cameraInput.files[0];
      cameraInput.value = ''; // Allow re-selecting the same file.
      if (!file) return;

      statusMessage.textContent = 'Analyzing photo...';
      setBusy(true);
      try {
        const image = await fileToScaledBase64(file);
        const result = await findPhotoByMatch({ image });
        const photoId = result.data && result.data.photoId;
        if (photoId) {
          statusMessage.textContent = 'Match found! Redirecting...';
          window.location.href = photoUrl(photoId);
          return;
        }
        statusMessage.textContent = 'Sorry, no close match was found. Try again a little closer, with less glare.';
      } catch (error) {
        console.error('Visual search failed:', error && error.code);
        statusMessage.textContent = errorMessage(error);
      }
      setBusy(false);
    });
  }

  /** Warms up the visual-search function so the first scan is quicker. */
  function warmUpScan() {
    firebase.functions().httpsCallable('findphotobymatch')({ warmup: true }).catch(() => {});
  }

  window.Gallery = { el, photoUrl, safeImageUrl, isEditor, errorMessage, initAuthNav, initScan, warmUpScan };
})();
