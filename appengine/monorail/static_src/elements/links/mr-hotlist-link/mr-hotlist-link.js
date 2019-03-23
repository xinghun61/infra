// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

/**
 * `<mr-hotlist-link>`
 *
 * Displays a link to a hotlist.
 *
 */
export class MrHotlistLink extends PolymerElement {
  static get template() {
    return html`
      <a
        href$="/u/[[hotlist.ownerRef.userId]]/hotlists/[[hotlist.name]]"
        title$="[[hotlist.name]] - [[hotlist.summary]]"
      >
        [[hotlist.name]]</a>
    `;
  }

  static get is() {
    return 'mr-hotlist-link';
  }

  static get properties() {
    return {
      hotlist: Object,
    };
  }
}
customElements.define(MrHotlistLink.is, MrHotlistLink);
