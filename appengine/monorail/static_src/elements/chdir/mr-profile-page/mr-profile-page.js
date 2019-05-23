// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {prpcClient} from 'prpc-client-instance.js';

import 'elements/framework/mr-header/mr-header.js';
import '../mr-activity-table/mr-activity-table.js';
import '../mr-comment-table/mr-comment-table.js';

/**
 * `<mr-profile-page>`
 *
 * The main entry point for a Monorail web components profile.
 *
 */
export class MrProfilePage extends LitElement {
  static get styles() {
    return css`
      .history-container {
        padding: 1em 16px;
        display: flex;
        flex-direction: column;
        min-height: 100%;
        box-sizing: border-box;
        flex-grow: 1;
      }
      mr-comment-table {
        width: 100%;
        margin-bottom: 1em;
        box-sizing: border-box;
      }
      mr-activity-table {
        width: 70%;
        flex-grow: 0;
        margin: auto;
        margin-bottom: 5em;
        height: 200px;
        box-sizing: border-box;
      }
      .metadata-container {
        font-size: var(--chops-main-font-size);
        border-right: var(--chops-normal-border);
        width: 15%;
        min-width: 256px;
        flex-grow: 0;
        flex-shrink: 0;
        box-sizing: border-box;
        min-height: 100%;
      }
      .container-outside {
        box-sizing: border-box;
        width: 100%;
        max-width: 100%;
        margin: auto;
        padding: 0.75em 8px;
        display: flex;
        align-items: stretch;
        justify-content: space-between;
        flex-direction: row;
        flex-wrap: no-wrap;
        flex-grow: 0;
        min-height: 100%;
      }
      .profile-data {
        text-align: center;
        padding-top: 40%;
        font-size: var(--chops-main-font-size);
      }
    `;
  }

  render() {
    return html`
      <mr-header
        .userDisplayName=${this.user}
        .loginUrl=${this.loginUrl}
        .logoutUrl=${this.logoutUrl}
      >
        <span slot="subheader">
          &gt; Viewing Profile: ${this.viewedUser}
        </span>
      </mr-header>
      <div class="container-outside">
        <div class="metadata-container">
          <div class="profile-data">
            ${this.viewedUser} <br>
            <b>Last visit:</b> ${this.lastVisitStr} <br>
            <b>Starred Developers:</b>
            ${this.starredUsers.length ? this.starredUsers.join(', ') : 'None'}
          </div>
        </div>
        <div class="history-container">
          ${this.user === this.viewedUser ? html`
            <mr-activity-table
              .comments=${this.comments}
              @dateChange=${this._changeDate}
            ></mr-activity-table>
          `: ''}
          <mr-comment-table
            .user=${this.viewedUser}
            .viewedUserId=${this.viewedUserId}
            .comments=${this.comments}
            .selectedDate=${this.selectedDate}>
          </mr-comment-table>
        </div>
      </div>
    `;
  }

  static get properties() {
    return {
      user: {type: String},
      logoutUrl: {type: String},
      loginUrl: {type: String},
      viewedUser: {type: String},
      viewedUserId: {type: Number},
      lastVisitStr: {type: String},
      starredUsers: {type: Array},
      comments: {type: Array},
      selectedDate: {type: Number},
    };
  }

  updated(changedProperties) {
    if (changedProperties.has('viewedUserId')) {
      this._fetchActivity();
    }
  }

  async _fetchActivity() {
    const commentMessage = {
      userRef: {
        userId: this.viewedUserId,
      },
    };

    const resp = await prpcClient.call(
      'monorail.Issues', 'ListActivities', commentMessage
    );

    this.comments = resp.comments;
  }

  _changeDate(e) {
    if (!e.detail) return;
    this.selectedDate = e.detail.date;
  }
}

customElements.define('mr-profile-page', MrProfilePage);
