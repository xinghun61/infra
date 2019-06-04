// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {prpcClient} from 'prpc.js';

import 'announcements-table.js';
import 'announcement-input.js';

import {SHARED_STYLES} from 'shared-styles.js';

export class ChopsAnnouncements extends LitElement {
  static get properties() {
    return {
      isTrooper: {type: Boolean},
      liveAnnouncements: {type: Array},
    };
  }

  firstUpdated() {
    this._fetchLiveAnnouncements();
  }

  static get styles() {
    return [SHARED_STYLES, css`
      .round-icon {
        border-radius: 25px;
        display: table;
        width: 48px;
        height: 24px;
        margin: 2px;
      }
      .round-icon p {
        display: table-cell;
        text-align: center;
        vertical-align: middle;
        color: white;
        font-weight: bolder;
      }
      .live {
        background-color: red;
      }
    `];
  }
  render() {
    return html`
      <div class="round-icon live small"><p>LIVE</p></div>
      <announcements-table
        id="live-announcements-table"
        .isTrooper="${this.isTrooper}"
        .announcements="${this.liveAnnouncements}"
        @announcements-changed=${this._fetchLiveAnnouncements}
      ></announcements-table>
      ${this.isTrooper ? html `
        <announcement-input
          @announcement-created=${this._fetchLiveAnnouncements}
        ></announcement-input>
      ` : ''}
    `;
  }

  async _fetchLiveAnnouncements() {
    const fetchLiveMessage = {
      retired: false,
    };
    const resp = await prpcClient.call(
      'dashboard.ChopsAnnouncements', 'SearchAnnouncements', fetchLiveMessage);
    this.liveAnnouncements = resp.announcements;
  }
}

customElements.define('chops-announcements', ChopsAnnouncements);
