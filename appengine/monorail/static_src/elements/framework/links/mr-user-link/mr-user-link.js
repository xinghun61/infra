// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import {connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';


const NULL_DISPLAY_NAME_VALUES = ['----', 'a_deleted_user'];

/**
 * `<mr-user-link>`
 *
 * Displays a link to a user profile.
 *
 */
export class MrUserLink extends connectStore(LitElement) {
  static get styles() {
    return css`
      :host {
        display: inline-block;
        white-space: nowrap;
      }
      i.inline-icon {
        font-size: var(--chops-icon-font-size);
        color: #B71C1C;
        vertical-align: bottom;
        cursor: pointer;
      }
      i.material-icons[hidden] {
        display: none;
      }
      .availability-notice {
        color: #B71C1C;
        font-weight: bold;
      }
    `;
  }

  static get properties() {
    return {
      referencedUsers: {
        type: Object,
      },
      showAvailabilityIcon: {
        type: Boolean,
      },
      showAvailabilityText: {
        type: Boolean,
      },
      userRef: {
        type: Object,
        attribute: 'userref',
      },
    };
  }

  constructor() {
    super();
    this.userRef = {};
    this.referencedUsers = new Map();
    this.showAvailabilityIcon = false;
    this.showAvailabilityText = false;
  }

  stateChanged(state) {
    this.referencedUsers = issue.referencedUsers(state);
  }

  render() {
    const availability = this._getAvailability();
    const userLink = this._getUserLink();
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <i
        id="availability-icon"
        class="material-icons inline-icon"
        title="${availability}"
        ?hidden="${!(this.showAvailabilityIcon && availability)}"
      >schedule</i>
      <a
        id="user-link"
        href="${userLink}"
        title="${this.userRef.displayName}"
        ?hidden="${!userLink}"
      >${this.userRef.displayName}</a>
      <span
        id="user-text"
        ?hidden="${userLink}"
      >${this.userRef.displayName}</span>
      <div
        id="availability-text"
        class="availability-notice"
        title="${availability}"
        ?hidden="${!(this.showAvailabilityText && availability)}"
      >${availability}</div>
    `;
  }

  _getAvailability() {
    if (!this.userRef || !this.referencedUsers) return '';
    const user = this.referencedUsers.get(this.userRef.displayName) || {};
    return user.availability;
  }

  _getUserLink() {
    if (!this.userRef || !this.userRef.displayName ||
        NULL_DISPLAY_NAME_VALUES.includes(this.userRef.displayName)) return '';
    return `/u/${this.userRef.userId || this.userRef.displayName}`;
  }
}
customElements.define('mr-user-link', MrUserLink);
