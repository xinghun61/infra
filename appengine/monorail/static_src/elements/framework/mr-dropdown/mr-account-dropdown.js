// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import './mr-dropdown.js';

/**
 * `<mr-account-dropdown>`
 *
 * Account dropdown menu for Monorail.
 *
 */
export class MrAccountDropdown extends LitElement {
  static get styles() {
    return css`
        :host {
          position: relative;
          display: inline-block;
          height: 100%;
          font-size: inherit;
        }
    `;
  }

  render() {
    return html`
      <mr-dropdown
        .text=${this.userDisplayName}
        .items=${this.items}
        .icon="arrow_drop_down"
      ></mr-dropdown>
    `;
  }

  static get properties() {
    return {
      userDisplayName: String,
      logoutUrl: String,
      loginUrl: String,
    };
  }

  get items() {
    return [
      {text: 'Switch accounts', url: this.loginUrl},
      {separator: true},
      {text: 'Profile', url: `/u/${this.userDisplayName}`},
      {text: 'Updates', url: `/u/${this.userDisplayName}/updates`},
      {text: 'Settings', url: '/hosting/settings'},
      {text: 'Saved queries', url: `/u/${this.userDisplayName}/queries`},
      {text: 'Hotlists', url: `/u/${this.userDisplayName}/hotlists`},
      {separator: true},
      {text: 'Sign out', url: this.logoutUrl},
    ];
  }
}

customElements.define('mr-account-dropdown', MrAccountDropdown);
