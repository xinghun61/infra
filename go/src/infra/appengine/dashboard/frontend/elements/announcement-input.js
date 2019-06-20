// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {prpcClient} from 'prpc.js';

import {SHARED_STYLES} from 'shared-styles.js';

/**
 * `<announcement-input>`
 *
 * An element that lets troopers create announcements.
 *
 */
export class AnnouncementInput extends LitElement {
  static get properties() {
    return {
      errorMessage: {type: String},
      disabled: {type: Boolean},
    };
  }

  constructor() {
    super();
    this.disabled = true;
  }

  static get styles() {
    return [SHARED_STYLES, css`
      :host {
        font-family: Roboto, Noto, sans-serif;
      }
      button {
        background-color: #649af4;
        color: white;
        font-weight: bolder;
        border: none;
        cursor: pointer;
        border-radius: 6px;
        padding: 0.25em 8px;
        margin: 0;
        margin-right: 4px;
        float: right;
      }
      button:disabled {
        background-color: grey;
      }
      textarea {
        width: 100%;
      }
      .tooltip {
        position: relative;
        float: right;
      }
      .tooltip .tooltip-text {
        visibility: hidden;
        width: 350px;
        padding: 5px;
        background-color: grey;
        color: white;
        text-align: center
        margin: 10px;
        border-radius: 6px;
        position: absolute;
        z-index: 1;

        right: 105%;
        top: -25px;
      }
      .tooltip:hover .tooltip-text {
        visibility: visible;
      }
    `];
  }

  // TODO(jojwang): use chops-button when shared.
  render() {
    return html`
      <div class="tooltip">
        <span class="tooltip-text">
          Announce a Gerrit service disruption by creating an
          announcement below to have it displayed to all
          users in chromium-review.googlesource.com.
          When the disruption is over, 'retire' the announcement,
          so it is no longer shown to our users.
        </span>
        &#9432;
      </div>
      <textarea
        id="announcementInput"
        @input="${this._disabledUpdateButton}"
        cols="80"
        rows="3"
        placeholder="Create a gerrit announcement"
      ></textarea>
      <button
        id="createButton"
        ?disabled=${this.disabled}
        @click="${this._createAnnouncementHandler}"
      >ANNOUNCE</button>
      ${this.errorMessage ? html`
        <span class=error>${this.errorMessage}</span>
      ` : ''}
    `;
  }

  _disabledUpdateButton() {
    if (this.shadowRoot.getElementById('announcementInput').value == '') {
      this.disabled = true;
    } else {
      this.disabled = false;
    }
  }

  _clearText() {
    this.shadowRoot.getElementById('announcementInput').value = '';
    this._disabledUpdateButton();
  }

  async _createAnnouncementHandler() {
    const message = {
      messageContent: this.shadowRoot.getElementById('announcementInput').value,
      platforms: [
        {name: 'gerrit'},
      ],
    };
    const respPromise = prpcClient.call(
      'dashboard.ChopsAnnouncements', 'CreateLiveAnnouncement', message);
    respPromise.then((resp) => {
      this._clearText();
      this.errorMessage = '';
      this.dispatchEvent(new CustomEvent('announcement-created'));
    }).catch((reason) => {
      this.errorMessage = `Failed to create announcement: ${reason}`;
    });
  }
}
customElements.define('announcement-input', AnnouncementInput);
