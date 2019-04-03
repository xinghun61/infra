// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {ReduxMixin} from '../../redux/redux-mixin.js';
import * as issue from '../../redux/issue.js';

/**
 * `<mr-user-link>`
 *
 * Displays a link to a user profile.
 *
 */
export class MrUserLink extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <style>
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
        .availability-notice {
          color: #B71C1C;
          font-weight: bold;
        }
      </style>
      <template is="dom-if" if="[[_and(showAvailabilityIcon, _availability)]]">
        <i
          id="availabilityIcon"
          class="material-icons inline-icon"
          title="[[_availability]]"
        >schedule</i>
      </template>
      <template is="dom-if" if="[[_userId]]">
        <a id="userLink" href\$="/u/[[_userId]]" title\$="[[_email]]">
          [[_email]]</a>
      </template>
      <template is="dom-if" if="[[!_userId]]">
        <span id="userText">[[_email]]</span>
      </template>
      <template is="dom-if" if="[[_and(showAvailabilityText, _availability)]]">
        <br />
        <span
          id="availabilityText"
          class="availability-notice"
          title="[[_availability]]"
        >[[_availability]]</span>
      </template>
    `;
  }
  static get is() {
    return 'mr-user-link';
  }

  static get properties() {
    return {
      userRef: Object,
      referencedUsers: Object,
      showAvailabilityIcon: Boolean,
      showAvailabilityText: Boolean,
      _availability: String,
      _email: String,
      _userId: String,
    };
  }

  static get observers() {
    return [
      '_computeProperties(userRef, referencedUsers)',
    ];
  }

  static mapStateToProps(state, element) {
    return {
      referencedUsers: issue.referencedUsers(state),
    };
  }

  _computeProperties(userRef, referencedUsers, showAvailability) {
    if (!userRef) return {};
    this._email = userRef.displayName;
    this._userId = userRef.userId || null;
    if (referencedUsers) {
      const user = referencedUsers.get(userRef.displayName) || {};
      this._availability = user.availability;
    }
  }

  _and(a, b) {
    return a && b;
  }
}
customElements.define(MrUserLink.is, MrUserLink);
