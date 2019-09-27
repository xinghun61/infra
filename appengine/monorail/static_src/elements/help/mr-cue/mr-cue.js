// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import qs from 'qs';
import {store, connectStore} from 'reducers/base.js';
import * as user from 'reducers/user.js';
import * as issue from 'reducers/issue.js';
import * as project from 'reducers/project.js';
import 'elements/chops/chops-button/chops-button.js';
import 'elements/chops/chops-dialog/chops-dialog.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';
import {prpcClient} from 'prpc-client-instance.js';

/**
 * `<mr-cue>`
 *
 * An element that displays one of a set of predefined help messages
 * iff that message is appropriate to the current user and page.
 *
 * TODO: Factor this class out into a base view component and separate
 * usage-specific components, such as those for user prefs.
 *
 */
export class MrCue extends connectStore(LitElement) {
  constructor() {
    super();
    this.prefs = new Map();
    this.issue = null;
    this.referencedUsers = new Map();
    this.nondismissible = false;
    this.hidden = this._shouldBeHidden(this.signedIn, this.prefsLoaded,
        this.cuePrefName, this.message);
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
      hidden: {
        type: Boolean,
        reflect: true,
      },
    };
  }

  static get styles() {
    return [SHARED_STYLES, css`
      :host {
        display: block;
        margin: 2px 0;
        padding: 2px 4px 2px 8px;
        background: var(--chops-notice-bubble-bg);
        border: var(--chops-notice-border);
        text-align: center;
      }
      :host([centered]) {
        display: flex;
        justify-content: center;
      }
      :host([hidden]) {
        display: none;
      }
      button[hidden] {
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
      <button
        @click=${this.dismiss}
        title="Don't show this message again."
        ?hidden=${this.nondismissible}>
        <i class="material-icons">close</i>
      </button>
      <div id="message">${this.message}</div>
    `;
  }

  get message() {
    if (this.cuePrefName === 'code_of_conduct') {
      return html`
        Please keep discussions respectful and constructive.
        See our
        <a href="${this.codeOfConductUrl}"
           target="_blank">code of conduct</a>.
        `;
    } else if (this.cuePrefName === 'availability_msgs') {
      if (this._availablityMsgsRelevant(this.issue)) {
        return html`
          <b>Note:</b>
          Clock icons indicate that users may not be available.
          Tooltips show the reason.
          `;
      }
    } else if (this.cuePrefName === 'switch_to_parent_account') {
      if (this._switchToParentAccountRelevant()) {
        return html`
          You are signed in to a linked account.
          <a href="${this.loginUrl}">
             Switch to ${this.user.linkedParentRef.displayName}</a>.
          `;
      }
    } else if (this.cuePrefName === 'search_for_numbers') {
      if (this._searchForNumbersRelevant(this.jumpLocalId)) {
        return html`
          <b>Tip:</b>
          To find issues containing "${this.jumpLocalId}", use quotes.
          `;
      }
    }
  }

  get codeOfConductUrl() {
    const projectName = (this.project && this.project.config &&
                         this.project.config.projectName);
    // TODO(jrobbins): Store this in the DB and pass it via the API.
    if (projectName === 'fuchsia') {
      return 'https://fuchsia.dev/fuchsia-src/CODE_OF_CONDUCT';
    }
    return ('https://chromium.googlesource.com/' +
            'chromium/src/+/master/CODE_OF_CONDUCT.md');
  }

  updated(changedProperties) {
    const hiddenWatchProps = ['prefsLoaded', 'cuePrefName', 'signedIn',
      'prefs'];
    const shouldUpdateHidden = Array.from(changedProperties.keys())
        .some((propName) => hiddenWatchProps.includes(propName));
    if (shouldUpdateHidden) {
      this.hidden = this._shouldBeHidden(this.signedIn, this.prefsLoaded,
          this.cuePrefName, this.message);
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

  _shouldBeHidden(signedIn, prefsLoaded, cuePrefName, message) {
    if (signedIn && !prefsLoaded) return true;
    if (this.alreadyDismissed(cuePrefName)) return true;
    return !message;
  }

  stateChanged(state) {
    this.project = project.project(state);
    this.issue = issue.issue(state);
    this.referencedUsers = issue.referencedUsers(state);
    this.user = user.user(state);
    this.prefs = user.prefs(state);
    this.signedIn = this.user && this.user.userId;
    this.prefsLoaded = user.user(state).prefsLoaded;

    const queryString = window.location.search.substring(1);
    const queryParams = qs.parse(queryString);
    const q = queryParams.q;
    if (q && q.match(new RegExp('^\\d+$'))) {
      this.jumpLocalId = Number(q);
    }
  }

  alreadyDismissed(pref) {
    return this.prefs && this.prefs.get(pref) === 'true';
  }

  dismiss() {
    const newPrefs = [{name: this.cuePrefName, value: 'true'}];
    store.dispatch(user.setPrefs(newPrefs, this.signedIn));
  }
}

customElements.define('mr-cue', MrCue);
