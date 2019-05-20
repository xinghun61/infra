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
export class MrCue extends connectStore(LitElement) {
  constructor() {
    super();
    this.prefs = new Map();
  }

  static get properties() {
    return {
      signedIn: {type: Boolean},
      cuePrefName: {type: String},
      prefs: {type: Object},
      prefsLoaded: {type: Boolean},
    };
  }

  static get styles() {
    return [SHARED_STYLES, css`
      .cue {
        margin: 2px 0;
        padding: 2px 4px;
        background: var(--chops-notice-bubble-bg);
        border:  var(--chops-notice-border);
        text-align: center;
      }
      .cue[hidden] {
        visibility: hidden;
      }
      i.material-icons {
       float: right;
       font-size: 14px;
       padding: 2px;
      }
      i.material-icons:hover {
        background: rgba(0, 0, 0, .2);
      }
    `];
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <div class="cue" ?hidden=${this.hidden}>
        ${this.message}
        <i class="material-icons"
           title="Don't show this message again."
           @click=${this.dismiss}
           >close</i>
      </div>
    `;
  }

  get message() {
    switch (this.cuePrefName) {
      case 'code_of_conduct':
        return html`
          Please keep discussions respectful and constructive.
          See our
          <a href="https://chromium.googlesource.com/chromium/src/+/master/CODE_OF_CONDUCT.md"
             target="_blank">code of conduct</a>.
          `;
    }
  }

  stateChanged(state) {
    this.prefs = user.user(state).prefs;
    this.prefsLoaded = user.user(state).prefsLoaded;
  }

  get hidden() {
    if (this.signedIn && !this.prefsLoaded) return true;
    if (this.alreadyDismissed(this.cuePrefName)) return true;
    return !this.message;
  }

  alreadyDismissed(pref) {
    return this.prefs.get(pref) === 'true';
  }

  dismiss() {
    this.setDismissedCue(this.cuePrefName);
  }

  setDismissedCue(pref) {
    const newPrefs = [{name: pref, value: 'true'}];
    if (this.signedIn) {
      // TODO(jrobbins): Move some of this into user.js.
      const message = {prefs: newPrefs};
      const setPrefsCall = prpcClient.call(
        'monorail.Users', 'SetUserPrefs', message);
      setPrefsCall.then((resp) => {
        store.dispatch(user.fetchPrefs());
      }).catch((reason) => {
        console.error('SetUserPrefs failed: ' + reason);
      });
    } else {
      store.dispatch(user.setPrefs(newPrefs));
    }
  }
}

customElements.define('mr-cue', MrCue);
