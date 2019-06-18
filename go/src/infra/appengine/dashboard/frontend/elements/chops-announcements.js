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
      retiredAnnouncements: {type: Array},
      _liveErrorMessage: {type: String},
      _retiredErrorMessage: {type: String},
    };
  }

  constructor() {
    super();
    this.liveAnnouncements = [];
    this.retiredAnnouncements = [];
  }

  firstUpdated() {
    this._fetchAnnouncements(0);
  }

  static get styles() {
    return [SHARED_STYLES, css`
      .round-icon {
        border-radius: 25px;
        display: table;
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
        width: 48px;
      }
      .retired {
        background-color: grey;
        width: 55px;
      }
      .table-area {
        padding: 15px;
      }
      announcement-input {
        width: 70%;
        display: block;
        margin-left: auto;
        margin-right: auto;
        padding: 10px;
      }
      .note {
        float: right;
        font-weight: bold;
      }
    `];
  }
  render() {
    return html`
      ${this.isTrooper ? html `
        <announcement-input
          @announcement-created=${this._fetchAnnouncements}
        ></announcement-input>
      ` : ''}
      <div class="table-area">
        <div class="round-icon live small"><p>LIVE</p></div>
        <announcements-table
          id="live-announcements-table"
          .isTrooper="${this.isTrooper}"
          .announcements="${this.liveAnnouncements}"
          @announcements-changed=${this._fetchAnnouncements}
        ></announcements-table>
        ${this._liveErrorMessage ? html`
          <span class=error>${this._liveErrorMessage}</span>
        ` : ''}
      </div>
      <div class="table-area">
        <div class="round-icon retired small"><p>RETIRED</p></div>
        <announcements-table
          id="retired-announcements-table"
          .isTrooper="${this.isTrooper}"
          retired
          .announcements="${this.retiredAnnouncements}"
        ></announcements-table>
        ${this._retiredErrorMessage ? html`
          <span class=error>${this._retiredErrorMessage}</span>
        ` : ''}
        <span class="note small">*Showing most recent retired announcements</span>
        <!--Add navigation for viewing older retired announcements. -->
      </div>
    `;
  }

  _fetchAnnouncements() {
    this._fetchLiveAnnouncements();
    this._fetchRetiredAnnouncements(0);
  }

  _fetchLiveAnnouncements() {
    const message = {
      retired: false,
    };
    const promise = prpcClient.call(
      'dashboard.ChopsAnnouncements', 'SearchAnnouncements', message);
    promise.then((resp) => {
      this.liveAnnouncements = resp.announcements;
      this._liveErrorMessage = '';
    }).catch((reason) => {
      this._liveErrorMessage = `Failed to fetch live announcements: ${reason}`;
    });
  }

  _fetchRetiredAnnouncements(offset) {
    const message = {
      retired: true,
      offset: offset,
      limit: 5,
    };
    const promise = prpcClient.call(
      'dashboard.ChopsAnnouncements', 'SearchAnnouncements', message);
    promise.then((resp) => {
      this.retiredAnnouncements = resp.announcements;
      this._retiredErrorMessage = '';
    }).catch((reason) => {
      this._retiredErrorMessage = `Failed to fetch retired announcements: ${reason}`;
    });
  }
}

customElements.define('chops-announcements', ChopsAnnouncements);
