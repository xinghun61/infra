// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../chops/chops-header/chops-header.js';
import '../mr-dropdown/mr-account-dropdown.js';

/**
 * `<mr-header>`
 *
 * The main entry point for a given launch issue.
 *
 */
export class MrHeader extends PolymerElement {
  static get template() {
    return html`
      <style>
        :host {
          z-index: 999;
        }
        chops-header {
          height: 40px;
          background-color: var(--chops-primary-header-bg);
          border-bottom: var(--chops-normal-border);
        }
        chops-header a {
          color: var(--chops-text-color);
          text-decoration: none;
        }
      </style>
      <chops-header app-title="Monorail" logo-src="/static/images/monorail.ico">
        <span slot="subheader">
          &gt;
          <a href\$="/p/[[projectName]]/">
            Project: [[projectName]]
          </a>
          <slot name="subheader"></slot>
        </span>
        <template is="dom-if" if="[[userDisplayName]]">
          <mr-account-dropdown
            user-display-name="[[userDisplayName]]"
            logout-url="[[logoutUrl]]"
            login-url="[[loginUrl]]"
          ></mr-dropdown>
        </template>
        <a href\$="[[loginUrl]]" hidden\$="[[userDisplayName]]">Sign in</a>
      </chops-header>
    `;
  }

  static get is() {
    return 'mr-header';
  }

  static get properties() {
    return {
      loginUrl: String,
      logoutUrl: String,
      projectName: String,
      userDisplayName: String,
    };
  }
}

customElements.define(MrHeader.is, MrHeader);
