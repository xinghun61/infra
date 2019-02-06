// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '../../node_modules/@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../chops/chops-header/chops-header.js';
import './mr-dropdown.js';

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
        chops-header {
          height: 40px;
          background-color: hsl(0, 0%, 95%);
          border-bottom: 1px solid hsl(0, 0%, 80%);
        }
        chops-header a {
          color: hsl(0, 0%, 13%);
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
          <mr-dropdown text="[[userDisplayName]]" items="[[_userMenuItems]]" icon="expand_more"></mr-dropdown>
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
      _userMenuItems: {
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

customElements.define(MrHeader.is, MrHeader);
