'use strict';
// chops-signin is a web component that manages signing into services using
// client-side OAuth via gapi.auth2. chops-signin visually indicates whether the
// user is signed in using either an icon or the user's profile picture. The
// signin or signout flow is initiated when the user clicks on this component.
// This component does not require Polymer, but if you are using Polymer, see
// chops-signin-aware.
//
// Usage:
//  html:
//   <chops-signin></chops-signin>
//  js:
//   window.AUTH_CLIENT_ID = '...';
//   window.addEventListener('user-update', ...);
//   const headers = await window.getAuthorizationHeaders();
//
// TODO(benjhayden): Remove the namespace and export functions when all clients
// import this as an ES6 module.
// TODO(benjhayden): Use async/await when all clients that need to support IE
// use a compiler like babel.
(function() {
  let resolveAuthInitializedPromise;
  const authInitializedPromise = new Promise(function(resolve) {
    resolveAuthInitializedPromise = resolve;
  });

  const callbackName = 'gapi' + Math.random();
  const gapiScript = document.createElement('script');
  gapiScript.src = 'https://apis.google.com/js/api.js?onload=' + callbackName;
  window[callbackName] = function() {
    gapi.load('auth2', onAuthLoaded);
    delete window[callbackName];
  };
  document.head.appendChild(gapiScript);

  function onAuthLoaded() {
    if (!window.gapi || !gapi.auth2) return;
    if (!document.body) {
      window.addEventListener('load', onAuthLoaded);
      return;
    }
    const auth = gapi.auth2.init({
      client_id: window.AUTH_CLIENT_ID,
      scope: 'email',
    });
    auth.currentUser.listen(function(user) {
      window.dispatchEvent(new CustomEvent('user-update', {detail: {user}}));
      // Start the cycle of setting the reload timer.
      window.getAuthorizationHeaders();
    });
    auth.then(
      function onFulfilled() {
        resolveAuthInitializedPromise();
      },
      function onRejected(error) {
        console.error(error);
      }
    );
  }

  const SVG_NS = 'http://www.w3.org/2000/svg';
  const SIZE = 32;
  const SIZE_PX = SIZE + 'px';

  const RELOAD_EARLY_MS = 60e3;
  let reloadTimerId;

  class ChopsSignin extends HTMLElement {
    connectedCallback() {
      this.style.cursor = 'pointer';
      this.style.strokeWidth = 0;
      this.style.width = SIZE_PX;
      this.style.height = SIZE_PX;
      this.img_ = document.createElement('img');
      this.img_.style.height = SIZE_PX;
      this.img_.style.borderRadius = '50%';
      this.img_.style.overflow = 'hidden';
      this.render_();
      this.addEventListener('click', this.onClick_.bind(this));
      window.addEventListener('user-update', this.onUserUpdate_.bind(this));
    }

    render_() {
      while (this.children.length) this.removeChild(this.children[0]);
      const profile = getUserProfileSync();
      if (!profile) {
        this.title = 'Signin with Google';
        this.appendChild(this.icon_);
        this.style.fill = 'var(--chops-signin-fill-color, red)';
        return;
      }
      this.title = 'Signout of ' + profile.getEmail();
      this.img_.src = profile.getImageUrl();
      if (this.img_.src) {
        this.appendChild(this.img_);
        return;
      }
      this.appendChild(this.icon_);
      this.style.fill = 'var(--chops-signout-fill-color, green)';
    }

    get icon_() {
      if (this.icon__) return this.icon__;
      this.icon__ = document.createElementNS(SVG_NS, 'svg');
      this.icon__.setAttribute('width', SIZE_PX);
      this.icon__.setAttribute('height', SIZE_PX);
      this.icon__.setAttribute('viewBox', '0 0 24 24');
      const path = document.createElementNS(SVG_NS, 'path');
      // iron-icons account-circle
      path.setAttributeNS(null, 'd', `
        M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0
        3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5
        0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29
        1.94-3.5 3.22-6 3.22z
      `);
      this.icon__.appendChild(path);
      return this.icon__;
    }

    onUserUpdate_() {
      this.render_();
    }

    onClick_() {
      return authInitializedPromise.then(function() {
        const auth = gapi.auth2.getAuthInstance();
        if (auth.currentUser.get().isSignedIn()) {
          return auth.signOut();
        } else {
          return auth.signIn();
        }
      });
    }
  }

  customElements.define('chops-signin', ChopsSignin);

  window.getAuthInstanceAsync = function() {
    return authInitializedPromise.then(function() {
      return gapi.auth2.getAuthInstance();
    });
  };

  window.getAuthorizationHeadersSync = function() {
    if (!window.gapi || !gapi.auth2) return undefined;
    const auth = gapi.auth2.getAuthInstance();
    if (!auth) return undefined;
    const user = auth.currentUser.get();
    if (!user) return {};
    const response = user.getAuthResponse();
    if (!response) return {};
    return {Authorization: response.token_type + ' ' + response.access_token};
  };

  window.getUserProfileSync = function() {
    if (!window.gapi || !gapi.auth2) return undefined;
    const auth = gapi.auth2.getAuthInstance();
    if (!auth) return undefined;
    const user = auth.currentUser.get();
    if (!user.isSignedIn()) return undefined;
    return user.getBasicProfile();
  };

  // This async version waits for gapi.auth2 to finish initializing before
  // getting the profile.
  window.getUserProfileAsync = function() {
    return authInitializedPromise.then(getUserProfileSync);
  };

  window.getAuthorizationHeaders = function() {
    return window.getAuthInstanceAsync().then(function(auth) {
      if (!auth) return undefined;
      const user = auth.currentUser.get();
      const response = user.getAuthResponse();
      if (response.expires_at === undefined) {
        // The user is not signed in.
        return undefined;
      }
      if ((response.expires_at - RELOAD_EARLY_MS) < new Date()) {
        // The token has expired or is about to expire, so reload it.
        return user.reloadAuthResponse();
      }
      return response;
    }).then(function(response) {
      if (!response) return {};
      if (!reloadTimerId) {
        // Automatically reload when the token is about to expire.
        const delayMs = response.expires_at - RELOAD_EARLY_MS + 1 - new Date();
        reloadTimerId = window.setTimeout(reloadAuthorizationHeaders, delayMs);
      }
      return {Authorization: response.token_type + ' ' + response.access_token};
    });
  };

  function reloadAuthorizationHeaders() {
    reloadTimerId = undefined;
    window.getAuthorizationHeaders().then(function(headers) {
      window.dispatchEvent(new CustomEvent(
          'authorization-headers-reloaded', {detail: {headers}}));
    });
  };
})();
