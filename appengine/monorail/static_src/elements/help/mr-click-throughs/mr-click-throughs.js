// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {store, connectStore} from 'elements/reducers/base.js';
import * as user from 'elements/reducers/user.js';
import 'elements/chops/chops-button/chops-button.js';
import 'elements/chops/chops-dialog/chops-dialog.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles.js';
import {prpcClient} from 'prpc-client-instance.js';

/**
 * `<mr-click-throughs>`
 *
 * An element that displays help dialogs that the user is required
 * to click through before they can participate in the community.
 *
 */
export class MrClickThroughs extends connectStore(LitElement) {
  constructor() {
    super();
  }

  static get properties() {
    return {
      userDisplayName: {type: String},
      prefs: {type: Object},
      prefsLoaded: {type: Boolean},
    };
  }

  static get styles() {
    return [SHARED_STYLES, css`
      :host {
        --chops-dialog-max-width: 800px;
      }
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
    `];
  }

  render() {
    return html`
      <chops-dialog
        id="privacyDialog"
        ?opened=${this._showPrivacyDialog}
        forced
      >
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
          <chops-button @click=${this.dismissPrivacyDialog}>
            Got it
          </chops-button>
        </div>
      </chops-dialog>

      <chops-dialog
        id="corpModeDialog"
        ?opened=${this._showCorpModeDialog}
        forced
      >
        <h2>This site hosts public issues in public projects</h2>

        <p>Unlike our internal issue tracker, this site makes most
        issues public, unless the issue is labeled with a Restrict-View-*
        label, such as Restrict-View-Google.</p>

        <p>Components are not used for permissions.  And, regardless of
        restriction labels, the issue reporter, owner,
        and Cc&apos;d users may always view the issue.</p>

        <p>Your account is a member of a user group that indicates that
        you may have access to confidential information.  To help prevent
        leaks when working in public projects, the issue tracker UX has
        been altered for you:</p>

        <ul>
         <li>When you open a new issue, the form will initially have a
         Restrict-View-Google label.  If you know that your issue does
         not contain confidential information, please remove the label.</li>
         <li>When you view public issues, a red banner is shown to remind
         you that any comments or attachments you post will be public.</li>
        </ul>

        <div class="edit-actions">
          <chops-button @click=${this.dismissCorpModeDialog}>
            Got it
          </chops-button>
        </div>
      </chops-dialog>
    `;
  }

  stateChanged(state) {
    this.prefs = user.prefs(state);
    this.prefsLoaded = user.user(state).prefsLoaded;
  }

  get _showPrivacyDialog() {
    if (!this.userDisplayName) return false;
    if (!this.prefsLoaded) return false;
    if (!this.prefs) return false;
    if (this.prefs.get('privacy_click_through') === 'true') return false;
    return true;
  }

  dismissPrivacyDialog() {
    this.dismissCue('privacy_click_through');
  }

  get _showCorpModeDialog() {
    // TODO(jrobbins): Replace this with a API call that gets the project.
    if (window.CS_env.projectIsRestricted) return false;
    if (!this.userDisplayName) return false;
    if (!this.prefsLoaded) return false;
    if (!this.prefs) return false;
    if (this.prefs.get('public_issue_notice') !== 'true') return false;
    if (this.prefs.get('corp_mode_click_through') === 'true') return false;
    return true;
  }

  dismissCorpModeDialog() {
    this.dismissCue('corp_mode_click_through');
  }

  dismissCue(pref) {
    const newPrefs = [{name: pref, value: 'true'}];
    store.dispatch(user.setPrefs(newPrefs, !!this.userDisplayName));
  }
}

customElements.define('mr-click-throughs', MrClickThroughs);
