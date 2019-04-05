// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, svg} from 'lit-element/lit-element.js';

/**
 * `chops-signin` is a web component that manages signing into services using
 * client-side OAuth via gapi.auth2. chops-signin visually indicates whether the
 * user is signed in using either an icon or the user's profile picture. The
 * signin or signout flow is initiated when the user clicks on this component.
 * This component does not require Polymer, but if you are using Polymer, see
 * chops-signin-aware.
 *
 * Usage:
 *  html:
 *   <chops-signin client-id=""...""></chops-signin>
 *  js:
 *   import * as signin from '@chopsui/chops-signin';
 *   window.addEventListener('user-update', ...);
 *   const headers = await signin.getAuthorizationHeaders();
 */
export class ChopsSignin extends LitElement {
  connectedCallback() {
    super.connectedCallback();
    this.addEventListener('click', this.onClick_.bind(this));
    window.addEventListener('user-update', this.onUserUpdate_.bind(this));
    this.clientIdChanged();
  }

  render() {
    const profile = getUserProfileSync();
    return html`
      <style>
     :host {
        --chops-signin-size: 32px;
        fill: var(--chops-signin-fill-color, red);
        cursor: pointer;
        stroke-width: 0;
        width: var(--chops-signin-size);
        height: var(--chops-signin-size);
      }
      img {
        height: var(--chops-signin-size);
        border-radius: 50%;
        overflow: hidden;
      }
       svg {
        width: var(--chops-signin-size);
        height: var(--chops-signin-size);
      }
      </style>
      ${this.errorMsg?
    html`<div class="error">Error: ${this.errorMsg}</div>` :
    html`${!profile ?
      html`Signin with Google ${this.icon_}` :
      html`Signout of ${profile.getEmail()} ${profile.getImageUrl() ?
        html`<img src="${profile.getImageUrl()}">` :
        html`${this.icon_}`}`}`}
    `;
  }

  static get properties() {
    return {
      profile: {
        type: Object,
      },
      clientId: {
        attribute: 'client-id',
        type: String,
      },
    };
  }

  clientIdChanged() {
    if (this.clientId) {
      delete this.errorMsg;
      init(this.clientId);
    } else {
      this.errorMsg = 'No client-id attribute set';
    }
  }

  attributeChangedCallback(name, oldval, newval) {
    super.attributeChangedCallback(name, oldval, newval);
    if (name == 'client-id') {
      this.clientIdChanged();
    }
  }

  get icon_() {
    return svg`<svg viewBox="0 0 24 24">
      <path
        d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0
        3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5
        0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29
        1.94-3.5 3.22-6 3.22z"></path>
    </svg>`;
  }

  onUserUpdate_() {
    this.profile = getUserProfileSync();
  }

  onClick_() {
    return authInitializedPromise.then(function() {
      const auth = gapi.auth2.getAuthInstance();
      if (auth.currentUser.get().isSignedIn()) {
        return auth.signOut();
      } else {
        return auth.signIn();
      }
    }).catch(function(err) {
      window.console.error(err);
    });
  }
}

customElements.define('chops-signin', ChopsSignin);

export function getAuthInstanceAsync() {
  return authInitializedPromise.then(function() {
    return gapi.auth2.getAuthInstance();
  });
};

export function getAuthorizationHeadersSync() {
  if (!gapi || !gapi.auth2) return undefined;
  const auth = gapi.auth2.getAuthInstance();
  if (!auth) return undefined;
  const user = auth.currentUser.get();
  if (!user) return {};
  const response = user.getAuthResponse();
  if (!response) return {};
  return {Authorization: response.token_type + ' ' + response.access_token};
};

export function getUserProfileSync() {
  if (!gapi || !gapi.auth2) return undefined;
  const auth = gapi.auth2.getAuthInstance();
  if (!auth) return undefined;
  const user = auth.currentUser.get();
  if (!user.isSignedIn()) return undefined;
  return user.getBasicProfile();
};

// This async version waits for gapi.auth2 to finish initializing before
// getting the profile.
export function getUserProfileAsync() {
  return authInitializedPromise.then(getUserProfileSync);
};

export function getAuthorizationHeaders() {
  return getAuthInstanceAsync()
    .then(function(auth) {
      if (!auth) return undefined;
      const user = auth.currentUser.get();
      const response = user.getAuthResponse();
      if (response.expires_at === undefined) {
        // The user is not signed in.
        return undefined;
      }
      if (response.expires_at < new Date()) {
        // The token has expired, so reload it.
        return user.reloadAuthResponse();
      }
      return response;
    })
    .then(function(response) {
      if (!response) return {};
      return {
        Authorization: response.token_type + ' ' + response.access_token,
      };
    });
};

let resolveAuthInitializedPromise;
const authInitializedPromise = new Promise(function(resolve) {
  resolveAuthInitializedPromise = resolve;
});

let gapi;

export function init(clientId) {
  const callbackName = 'gapi' + Math.random();
  const gapiScript = document.createElement('script');
  gapiScript.src = 'https://apis.google.com/js/api.js?onload=' + callbackName;

  // TODO: see about moving the script element during disconnectedCallback.
  function removeScript() {
    document.head.removeChild(gapiScript);
  }

  window[callbackName] = function(args) {
    gapi = window.gapi;
    window.gapi.load('auth2', onAuthLoaded);
    delete window[callbackName];
    removeScript();
  };
  gapiScript.onerror = removeScript;
  document.head.appendChild(gapiScript);

  function onAuthLoaded(args) {
    if (!window.gapi || !gapi.auth2) return;
    if (!document.body) {
      window.addEventListener('load', onAuthLoaded);
      return;
    }
    const auth = window.gapi.auth2.init({
      client_id: clientId,
      scope: 'email',
    });
    auth.currentUser.listen(function(user) {
      window.dispatchEvent(new CustomEvent('user-update', {detail: {user}}));
    });
    auth.then(
      function onFulfilled() {
        resolveAuthInitializedPromise();
      },
      function onRejected(error) {
        window.console.error(error);
      }
    );
  }
}