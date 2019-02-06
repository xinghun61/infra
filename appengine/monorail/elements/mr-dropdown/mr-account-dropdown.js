// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import './mr-dropdown.js';

/**
 * `<mr-account-dropdown>`
 *
 * Account dropdown menu for Monorail.
 *
 */
export class MrAccountDropdown extends PolymerElement {
  static get template() {
    return html`
      <mr-dropdown text="[[userDisplayName]]" items="[[items]]" icon="arrow_drop_down"></mr-dropdown>
    `;
  }

  static get is() {
    return 'mr-account-dropdown';
  }

  static get properties() {
    return {
      userDisplayName: String,
      logoutUrl: String,
      loginUrl: String,
      items: {
        type: Array,
        computed: '_computeUserMenuItems(userDisplayName, loginUrl, logoutUrl)',
      },
    };
  }

  _computeUserMenuItems(userDisplayName, loginUrl, logoutUrl) {
    return [
      {text: 'Switch accounts', url: loginUrl},
      {separator: true},
      {text: 'Profile', url: `/u/${userDisplayName}`},
      {text: 'Updates', url: `/u/${userDisplayName}/updates`},
      {text: 'Settings', url: '/hosting/settings'},
      {text: 'Saved queries', url: `/u/${userDisplayName}/queries`},
      {text: 'Hotlists', url: `/u/${userDisplayName}/hotlists`},
      {separator: true},
      {text: 'Sign out', url: logoutUrl},
    ];
  }
}

customElements.define(MrAccountDropdown.is, MrAccountDropdown);
