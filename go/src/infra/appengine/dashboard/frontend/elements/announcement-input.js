// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {prpcClient} from 'prpc.js';

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
    return css`
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
      }
      button:disabled {
        background-color: grey;
      }
      .error {
        color: red;
        font-size: 12px;
      }
    `;
  }

  // TODO(jojwang): use chops-button when shared.
  render() {
    return html`
      <textarea
        id="announcementInput"
        @input="${this._disabledUpdateButton}"
        cols="80"
        rows="3"
        placeholder="Create a gerrit announcement"
      ></textarea>
      <div>
        <button
          id="createButton"
          ?disabled=${this.disabled}
          @click="${this._createAnnouncementHandler}"
        >ANNOUNCE</button>
        ${this.errorMessage ? html`
          <span class=error>${this.errorMessage}</span>
        ` : ''}
      </div>
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
