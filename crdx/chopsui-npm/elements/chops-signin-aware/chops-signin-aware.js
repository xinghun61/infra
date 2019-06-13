// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement} from 'lit-element';
import {getAuthorizationHeadersSync, getUserProfileSync} from '../chops-signin';

// This component adapts chops-signin to an API that is more familiar to Polymer
// components. Use this table to convert from google-signin-aware:

// google-signin-aware                    chops-signin-aware
//                         *events*
// google-signin-aware-success            user-update
// google-signin-aware-signed-out         user-update
// signed-in-changed                      user-update
//                         *properties*
// signedIn                               signedIn
// (getAuthResponse())                    authHeaders
// clientId                               (set window.AUTH_CLIENT_ID)
// scopes                                 (not supported)
// height                                 (not supported)
// theme                                  (not supported)
// (user.getBasicProfile())               profile

export class ChopsSigninAware extends LitElement {
  static get properties() {
    return {
      authHeaders: {
        attribute: 'auth-headers',
        type: Object,
        readOnly: true,
      },
      profile: {
        attribute: 'profile',
        type: Object,
        readOnly: true,
      },
      signedIn: {
        attribute: 'signed-in',
        type: Boolean,
        readOnly: true,
      },
    };
  }

  constructor() {
    super();
    this._updateProperties();
  }

  connectedCallback() {
    // removeEventListener requires exactly the same function object that was
    // passed to addEventListener, so bind the listener methods.
    this._onUserUpdate = this._onUserUpdate.bind(this);
    this._onHeadersReloaded = this._onHeadersReloaded.bind(this);
    window.addEventListener('user-update', this._onUserUpdate);
    window.addEventListener(
      'authorization-headers-reloaded', this._onHeadersReloaded);
    this._onUserUpdate();
  }

  disconnectedCallback() {
    window.removeEventListener('user-update', this._onUserUpdate);
    window.removeEventListener(
      'authorization-headers-reloaded', this._onHeadersReloaded);
  }

  _updateProperties() {
    // Use private setters because these properties are read-only to prevent
    // clients from accidentally overwriting them.
    this.profile = getUserProfileSync();
    this.authHeaders = getAuthorizationHeadersSync();
    this.signedIn = !!this.profile;
  }

  _onHeadersReloaded(event) {
    this._updateProperties();
  }

  _onUserUpdate() {
    this._updateProperties();
    this.dispatchEvent(new CustomEvent('user-update'));
  }
}
customElements.define('chops-signin-aware', ChopsSigninAware);
