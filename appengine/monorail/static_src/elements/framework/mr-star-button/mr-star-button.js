// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {connectStore, store} from 'elements/reducers/base.js';
import * as user from 'elements/reducers/user.js';
import * as issue from 'elements/reducers/issue.js';
import {issueRefToString} from '../../shared/converters';

/**
 * `<mr-star-button>`
 *
 * A button for starring an issue.
 *
 */
export class MrStarButton extends connectStore(LitElement) {
  static get styles() {
    return css`
      :host {
        display: block;
      }
      button {
        background: none;
        border: none;
        cursor: pointer;
        padding: 0;
        margin: 0;
        display: flex;
        align-items: center;
      }
      button[disabled] {
        opacity: 0.5;
        cursor: default;
      }
      i.material-icons {
        font-size: var(--chops-icon-font-size);
        color: var(--chops-primary-icon-color);
      }
      i.material-icons.starred {
        color: var(--chops-blue-700);
      }
    `;
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <button class="star-button"
        @click=${this.toggleStar}
        ?disabled=${!this._canStar}
      >
        ${this._starredIssues.has(issueRefToString(this.issueRef)) ? html`
          <i class="material-icons starred" title="You've starred this issue">
            star
          </i>
        `: html`
          <i
            class="material-icons"
            title="${this._isLoggedIn ? 'Click' : 'Log in'} to star this issue"
          >
            star_border
          </i>
        `}
      </button>
    `;
  }

  static get properties() {
    return {
      /**
       * A reference to the issue that the star button interacts with.
       */
      issueRef: {type: Object},
      /**
       * Whether the issue is starred (used for accessing easily).
       */
      _starredIssues: {type: Set},
      /**
       * Whether the issue's star state is being fetched. This is taken from
       * the component's parent, which is expected to handle fetching initial
       * star state for an issue.
       */
      _fetchingIsStarred: {type: Boolean},
      /**
       * If the issue is currently being starred. This component handles the
       * starring action up until the point when the action is dispatched to
       * Redux.
       */
      _starringIssue: {type: Boolean},
      /**
       * The currently logged in user. Required to determine if the user can
       * star.
       */
      _isLoggedIn: {type: Object},
    };
  }

  stateChanged(state) {
    const currentUser = user.user(state);
    this._isLoggedIn = currentUser && currentUser.userId;
    // TODO(zhangtiff): Rework Redux to store separate requests for different
    // issues being starred.
    this._starringIssue = issue.requests(state).star.requesting;
    this._starredIssues = issue.starredIssues(state);
    this._fetchingIsStarred = issue.requests(state).fetchIsStarred.requesting;
  }


  get _canStar() {
    return this._isLoggedIn && !this._fetchingIsStarred && !this._starringIssue;
  }

  toggleStar() {
    if (!this._canStar) return;
    const newIsStarred = !this._starredIssues.has(
      issueRefToString(this.issueRef));
    // This component assumes that the user of this component is connected to
    // Redux and will update their star state based on this.
    store.dispatch(issue.star(this.issueRef, newIsStarred));
  }
}

customElements.define('mr-star-button', MrStarButton);
