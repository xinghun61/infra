// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html} from 'lit-element';

/**
 * `<mr-hotlist-link>`
 *
 * Displays a link to a hotlist.
 *
 */
export class MrHotlistLink extends LitElement {
  render() {
    if (!this.hotlist) return html``;
    return html`
      <a
        href="/u/${this.hotlist.ownerRef && this.hotlist.ownerRef.userId}/hotlists/${this.hotlist.name}"
        title="${this.hotlist.name} - ${this.hotlist.summary}"
      >
        ${this.hotlist.name}</a>
    `;
  }

  static get properties() {
    return {
      hotlist: {type: Object},
    };
  }
}
customElements.define('mr-hotlist-link', MrHotlistLink);
