// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {connectStore} from 'elements/reducers/base.js';
import * as user from 'elements/reducers/user.js';
import 'elements/chops/chops-button/chops-button.js';
import 'elements/chops/chops-dialog/chops-dialog.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles.js';

/**
 * `<mr-cues>`
 *
 * An element that displays brief on-page help or help
 * dialogs at appropriate times based on the issue being
 * viewed and the user's preferences.
 *
 */
export class MrCues extends connectStore(LitElement) {
  constructor() {
    super();
    this.dismissedDialog = false;
  }

  static get properties() {
    return {
      userDisplayName: {type: String},
      prefs: {type: Object},
      prefsLoaded: {type: Boolean},
      dismissedDialog: {type: Boolean},
    };
  }

  static get styles() {
    return [SHARED_STYLES, css`
      h2 {
        margin-top: 0;
        display: flex;
        justify-content: space-between;
        font-weight: normal;
        border-bottom: 2px solid white;
        font-size: var(--chops-large-font-size);
        padding-bottom: 0.5em;
      }
      .edit-actions {
        width: 100%;
        margin: 0.5em 0;
        text-align: right;
      }
      i.material-icons {
        color: #FF6F00;
        margin-right: 4px;
      }
    `];
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <chops-dialog
        id="privacyDialog"
        ?opened=${this._showPrivacyDialog}
        forced>
        <div class="dialog-content">
          <h2>Email display settings</h2>

          <p>There is a <a href="/hosting/settings">setting</a> to control how
          your email address appears on comments and issues that you post.</p>

          <p>Project members will always see your full email address.  By
          default, other users who visit the site will see an
          abbreviated version of your email address.</p>

          <p>If you do not wish your email address to be shared, there
          are other ways to <a
          href="http://www.chromium.org/getting-involved">get
          involved</a> in the community.  To report a problem when using
          the Chrome browser, you may use the "Report an issue..."  item
          on the "Help" menu.</p>


          <div class="edit-actions">
              <chops-button @click=${this.dismissDialog}>
              Got it
            </button>
          </div>
        </div>
      </chops-dialog>
    `;
  }

  stateChanged(state) {
    this.prefs = user.user(state).prefs;
    this.prefsLoaded = user.user(state).prefsLoaded;
  }

  get _showPrivacyDialog() {
    if (!this.userDisplayName) return false;
    if (!this.prefsLoaded) return false;
    if (this.dismissedDialog) return false;
    if (!this.prefs) return false;
    if (this.prefs.get('privacy_click_through') === 'true') return false;
    return true;
  }

  dismissDialog() {
    this.dismissedDialog = true;
    window.prpcClient.call('monorail.Users', 'SetUserPrefs', {
      prefs: [{name: 'privacy_click_through', value: 'true'}],
    });
  }
}

customElements.define('mr-cues', MrCues);
