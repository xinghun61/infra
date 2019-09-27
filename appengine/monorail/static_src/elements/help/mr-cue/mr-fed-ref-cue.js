// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {html, css} from 'lit-element';
import * as user from 'reducers/user.js';
import * as issue from 'reducers/issue.js';
import {store} from 'reducers/base.js';
import 'elements/chops/chops-button/chops-button.js';
import 'elements/chops/chops-dialog/chops-dialog.js';
import {fromShortlink, GoogleIssueTrackerIssue} from 'shared/federated.js';
import {MrCue} from './mr-cue.js';

/**
 * `<mr-fed-ref-cue>`
 *
 * Displays information and login/logout links for the federated references
 * info popup.
 *
 */
export class MrFedRefCue extends MrCue {
  static get properties() {
    return {
      ...MrCue.properties,
      fedRefShortlink: {type: String},
    };
  }

  static get styles() {
    return [
      ...MrCue.styles,
      css`
        :host {
          margin: 0;
          width: 120px;
          font-size: 11px;
        }
      `,
    ];
  }

  get message() {
    const fedRef = fromShortlink(this.fedRefShortlink);
    if (fedRef && fedRef instanceof GoogleIssueTrackerIssue) {
      let authLink;
      if (this.user && this.user.gapiEmail) {
        authLink = html`
          <br /><br />
          <a href="#"
            @click=${() => store.dispatch(user.initGapiLogout())}
          >Sign out</a>
          <br />
          (for references only)
        `;
      } else {
        const clickLoginHandler = async () => {
          await store.dispatch(user.initGapiLogin(this.issue));
          // Re-fetch related issues.
          store.dispatch(issue.fetchRelatedIssues(this.issue));
        };
        authLink = html`
          <br /><br />
          Googlers, to enable viewing status & title,
          <a href="#"
            @click=${clickLoginHandler}
            >sign in here</a> with your Google email.
        `;
      }
      return html`
        This references an issue in the ${fedRef.trackerName} issue tracker.
        ${authLink}
      `;
    } else {
      return html`
        This references an issue in another tracker. Status not displayed.
      `;
    }
  }
}

customElements.define('mr-fed-ref-cue', MrFedRefCue);
