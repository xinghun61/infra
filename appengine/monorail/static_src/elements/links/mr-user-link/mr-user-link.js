// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {connectStore} from '../../redux/base.js';
import * as issue from '../../redux/issue.js';


const NULL_DISPLAY_NAME_VALUES = ['----', 'a deleted user'];

/**
 * `<mr-user-link>`
 *
 * Displays a link to a user profile.
 *
 */
export class MrUserLink extends connectStore(PolymerElement) {
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
      <template is="dom-if" if="[[_userLink]]">
        <a id="userLink" href$="[[_userLink]]" title$="[[userRef.displayName]]">
          [[userRef.displayName]]</a>
      </template>
      <template is="dom-if" if="[[!_userLink]]">
        <span id="userText">[[userRef.displayName]]</span>
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
      _userLink: {
        type: String,
        computed: '_computeUserLink(userRef)',
      },
    };
  }

  static get observers() {
    return [
      '_computeProperties(userRef, referencedUsers)',
    ];
  }

  stateChanged(state) {
    this.referencedUsers = issue.referencedUsers(state);
  }

  _computeProperties(userRef, referencedUsers) {
    if (!userRef) return {};
    if (referencedUsers) {
      const user = referencedUsers.get(userRef.displayName) || {};
      this._availability = user.availability;
    }
  }

  _computeUserLink(userRef) {
    if (!userRef || !Object.keys(userRef).length ||
      NULL_DISPLAY_NAME_VALUES.includes(userRef.displayName)) return '';
    return `/u/${userRef.userId ? userRef.userId : userRef.displayName}`;
  }

  _and(a, b) {
    return a && b;
  }
}
customElements.define(MrUserLink.is, MrUserLink);
