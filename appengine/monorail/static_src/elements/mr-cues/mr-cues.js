// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {connectStore} from '../redux/base.js';
import * as user from '../redux/user.js';
import '../chops/chops-button/chops-button.js';
import '../chops/chops-dialog/chops-dialog.js';
import '../shared/mr-shared-styles.js';

/**
 * `<mr-cues>`
 *
 * An element that displays brief on-page help or help
 * dialogs at appropriate times based on the issue being
 * viewed and the user's preferences.
 *
 */
export class MrCues extends connectStore(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style include="mr-shared-styles">
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
      </style>
      <chops-dialog id="privacyDialog" forced>
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
            <chops-button on-click="dismissDialog">
              Got it
            </button>
          </div>
        </div>
      </dialog>
    `;
  }

  static get properties() {
    return {
      userDisplayName: String,
      prefs: Object,
      prefsLoaded: Boolean,
      dismissedDialog: {
        type: Boolean,
        value: false,
      },
      showPrivacyDialog: {
        type: Boolean,
        computed:
        '_computeShowPrivacyDialog(prefs, prefsLoaded, dismissedDialog)',
      },
    };
  }

  stateChanged(state) {
    this.setProperties({
      prefs: user.user(state).prefs,
      prefsLoaded: user.user(state).prefsLoaded,
    });
  }

  static get observers() {
    return [
      '_showPrivacyDialogChanged(showPrivacyDialog)',
    ];
  }

  _computeShowPrivacyDialog(prefs, prefsLoaded, dismissedDialog) {
    if (!this.userDisplayName) return false;
    if (!prefsLoaded) return false;
    if (dismissedDialog) return false;
    if (!prefs) return false;
    if (prefs.get('privacy_click_through') === 'true') return false;
    return true;
  }

  _showPrivacyDialogChanged(showPrivacyDialog) {
    const privacyDialog = this.shadowRoot.querySelector('#privacyDialog');
    if (showPrivacyDialog) {
      privacyDialog.open();
    } else {
      privacyDialog.close();
    }
  }

  dismissDialog() {
    this.dismissedDialog = true;
    window.prpcClient.call('monorail.Users', 'SetUserPrefs', {
      prefs: [{name: 'privacy_click_through', value: 'true'}],
    });
  }

  static get is() {
    return 'mr-cues';
  }
}

customElements.define(MrCues.is, MrCues);
