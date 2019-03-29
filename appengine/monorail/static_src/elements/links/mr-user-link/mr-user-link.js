// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

/**
 * `<mr-user-link>`
 *
 * Displays a link to a user profile.
 *
 */
export class MrUserLink extends PolymerElement {
  static get template() {
    return html`
      <style>
        :host {
          display: inline-block;
        }
      </style>
      <template is="dom-if" if="[[userId]]">
        <a id="userLink" href\$="/u/[[userId]]" title\$="[[displayName]]">
          [[displayName]]</a>
      </template>
      <span id="userText" hidden\$="[[userId]]">
        [[displayName]]</span>
    `;
  }
  static get is() {
    return 'mr-user-link';
  }

  static get properties() {
    return {
      displayName: String,
      userId: String,
    };
  }
}
customElements.define(MrUserLink.is, MrUserLink);
