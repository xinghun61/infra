// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import qs from 'qs';
import {store, connectStore} from 'elements/reducers/base.js';
import * as user from 'elements/reducers/user.js';
import * as issue from 'elements/reducers/issue.js';
import 'elements/chops/chops-button/chops-button.js';
import 'elements/chops/chops-dialog/chops-dialog.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles.js';
import {prpcClient} from 'prpc-client-instance.js';

/**
 * `<mr-cue>`
 *
 * An element that displays one of a set of predefined help messages
 * iff that message is appropriate to the current user and page.
 *
 */
export class MrCue extends connectStore(LitElement) {
  constructor() {
    super();
    this.prefs = new Map();
    this.issue = null;
    this.referencedUsers = new Map();
    this.nondismissible = false;
  }

  static get properties() {
    return {
      issue: {type: Object},
      referencedUsers: {type: Object},
      user: {type: Object},
      cuePrefName: {type: String},
      nondismissible: {type: Boolean},
      prefs: {type: Object},
      prefsLoaded: {type: Boolean},
      jumpLocalId: {type: Number},
      loginUrl: {type: String},
    };
  }

  static get styles() {
    return [SHARED_STYLES, css`
      :host([centered]) {
        display: flex;
        justify-content: center;
      }
      .cue {
        margin: 2px 0;
        padding: 2px 4px 2px 8px;
        background: var(--chops-notice-bubble-bg);
        border:  var(--chops-notice-border);
        text-align: center;
      }
      .cue[hidden], button[hidden] {
        visibility: hidden;
      }
      i.material-icons {
        font-size: 14px;
      }
      button {
        background: none;
        border: none;
        float: right;
        padding: 2px;
        cursor: pointer;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
      }
      button:hover {
        background: rgba(0, 0, 0, .2);
      }
    `];
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <div class="cue" ?hidden=${this.hidden} id="message">
        <button
          @click=${this.dismiss}
          title="Don't show this message again."
          ?hidden=${this.nondismissible}
        >
          <i class="material-icons">close</i>
        </button>
        ${this.message}
      </div>
    `;
  }

  get message() {
    if (this.cuePrefName == 'code_of_conduct') {
      return html`
        Please keep discussions respectful and constructive.
        See our
        <a href="https://chromium.googlesource.com/chromium/src/+/master/CODE_OF_CONDUCT.md"
           target="_blank">code of conduct</a>.
        `;
    } else if (this.cuePrefName == 'availability_msgs') {
      if (this._availablityMsgsRelevant(this.issue)) {
        return html`
          <b>Note:</b>
          Clock icons indicate that users may not be available.
          Tooltips show the reason.
          `;
      }
    } else if (this.cuePrefName == 'switch_to_parent_account') {
      if (this._switchToParentAccountRelevant()) {
        return html`
          You are signed in to a linked account.
          <a href="${this.loginUrl}">
             Switch to ${this.user.linkedParentRef.displayName}</a>.
          `;
      }
    } else if (this.cuePrefName == 'search_for_numbers') {
      if (this._searchForNumbersRelevant(this.jumpLocalId)) {
        return html`
          <b>Tip:</b>
          To find issues containing "${this.jumpLocalId}", use quotes.
          `;
      }
    }
  }

  _availablityMsgsRelevant(issue) {
    if (!issue) return false;
    return (this._anyUnvailable([issue.ownerRef]) ||
            this._anyUnvailable(issue.ccRefs));
  }

  _anyUnvailable(userRefList) {
    if (!userRefList) return false;
    for (const userRef of userRefList) {
      if (userRef) {
        const participant = this.referencedUsers.get(userRef.displayName);
        if (participant && participant.availability) return true;
      }
    }
  }

  _switchToParentAccountRelevant() {
    return this.user && this.user.linkedParentRef;
  }

  _searchForNumbersRelevant(jumpLocalId) {
    return jumpLocalId;
  }

  stateChanged(state) {
    this.issue = issue.issue(state);
    this.referencedUsers = issue.referencedUsers(state);
    this.user = user.user(state);
    this.prefs = user.user(state).prefs;
    this.signedIn = this.user && this.user.userId;
    this.prefsLoaded = user.user(state).prefsLoaded;

    const queryString = window.location.search.substring(1);
    const queryParams = qs.parse(queryString);
    const q = queryParams.q;
    if (q && q.match(new RegExp('^\\d+$'))) {
      this.jumpLocalId = Number(q);
    }
  }

  get hidden() {
    if (this.signedIn && !this.prefsLoaded) return true;
    if (this.alreadyDismissed(this.cuePrefName)) return true;
    return !this.message;
  }

  alreadyDismissed(pref) {
    return this.prefs && this.prefs.get(pref) === 'true';
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
      store.dispatch(user.setPrefs(new Map([[pref, 'true']])));
    }
  }
}

customElements.define('mr-cue', MrCue);
