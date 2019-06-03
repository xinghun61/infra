// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {prpcClient} from 'prpc.js';

import {SHARED_STYLES} from 'shared-styles.js';

/**
 * `<announcements-table>`
 *
 * Table to display all retired or all live announcements.
 *
 */
export class AnnouncementsTable extends LitElement {
  static get properties() {
    return {
      isTrooper: {type: Boolean},
      announcements: {type: Array},
      retired: {type: Boolean},
    };
  }

  static get styles() {
    return [SHARED_STYLES, css`
      :host {
        font-family: Roboto, Noto, sans-serif;
      }
      button {
        background-color: transparent;
        border: none;
        color: #649af4;
        font-weight: bolder;
        cursor: pointer;
      }
      table {
        border-collapse: collapse;
        width: 100%;
      }
      td.announcement-content {
        width: 60%;
      }
      td > div.date {
        color: grey;
      }
      td.platforms {
        color: grey;
      }
      td, th {
        padding: 7px;
      }
      th {
        color: grey;
        font-size: .9em;
      }
      tr {
        background-color: white;
        text-align: center;
        border: solid #f4f4f4;
        border-width: .5px 0;
      }
      tr:first-child {
        border-top: none;
      }
      tr:last-child {
        border-bottom: none;
      }
    `];
  }

  render() {
    return html`
      <table cellspacing="0" cellpadding="0">
        <tbody>
          <tr class="header-row">
            ${this.isTrooper && !this.retired ? html`<th></th>` : ''}
            <th>Platforms</th>
            <th>Announcement</th>
            <th>Timestamp</th>
          </tr>

          ${(this.announcements && this.announcements.length
  ) ? this.announcements.map((ann) => html`
            <tr>
              ${this.isTrooper && !this.retired ? html`
                <td>
                  <button
                    data-annId="${ann.id}" @click=${this.retireAnnouncement}
                  >RETIRE</button>
                </td>` : ''}
              <td class="platforms">
                ${ann.platforms && ann.platforms.length ? ann.platforms.map(
    (plat) => html`
                   <div>${plat.name}</div>`) : html` <i>No platforms found</i>
                `}
              </td>
              <td class="announcement-content">${ann.messageContent}</td>
              <td class="small">
                <div class="date">${this._formatDate(ann.startTime)}</div>
                <div class="creator">${ann.creator}</div>
              </td>
            </tr>
          `) : html`
            <tr>
              <td
                colspan=${this.isTrooper && !this.retired ? '4' : '3'}
              ><i>No announcements.</i></td>
            </tr>
          `}
        </tbody>
      </table>
    `;
  }

  // TODO(jojwang): use chops-timestamp when it's shared.
  _formatDate(timeStr) {
    const date = new Date(timeStr);
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      timeZoneName: 'short',
    }).format(date);
  }

  retireAnnouncement(event) {
    const retireMessage = {
      announcementId: event.target.getAttribute('data-annId'),
    };
    const respPromise = prpcClient.call(
      'dashboard.ChopsAnnouncements', 'RetireAnnouncement', retireMessage);
    respPromise.then((resp) => {
      this.dispatchEvent(new CustomEvent('announcements-changed'));
    });
  }
}
customElements.define('announcements-table', AnnouncementsTable);
