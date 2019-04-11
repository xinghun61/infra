// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {PolymerElement, html} from '@polymer/polymer';

import {ReduxMixin} from '../../redux/redux-mixin.js';
import * as issue from '../../redux/issue.js';
import {arrayToEnglish} from '../../shared/helpers.js';


/**
 * `<mr-restriction-indicator>`
 *
 * Display for showing whether an issue is restricted.
 *
 */
export class MrRestrictionIndicator extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <style>
        :host {
          width: 100%;
          margin-top: 0;
          background-color: var(--monorail-metadata-toggled-bg);
          border-bottom: var(--chops-normal-border);
          font-size: var(--chops-main-font-size);
          padding: 0.25em 8px;
          box-sizing: border-box;
          display: flex;
          flex-direction: row;
          justify-content: flex-start;
          align-items: center;
        }
        :host([hidden]) {
          display: none;
        }
        i.material-icons {
          color: var(--chops-primary-icon-color);
          font-size: var(--chops-icon-font-size);
        }
        .lock-icon {
          margin-right: 4px;
        }
      </style>
      <i
        class="lock-icon material-icons"
        icon="lock"
      >
        lock
      </i>
      [[_restrictionText]]
    `;
  }

  static get is() {
    return 'mr-restriction-indicator';
  }

  static get properties() {
    return {
      hidden: {
        type: Boolean,
        reflectToAttribute: true,
        computed: '_computeHidden(isRestricted)',
      },
      restrictions: Object,
      isRestricted: {
        type: Boolean,
        value: false,
      },
      _restrictionText: {
        type: String,
        computed: '_computeRestrictionText(restrictions)',
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      restrictions: issue.restrictions(state),
      isRestricted: issue.isRestricted(state),
    };
  }

  _computeHidden(isRestricted) {
    return !isRestricted;
  }

  _computeRestrictionText(restrictions) {
    if (!restrictions) return;
    if ('view' in restrictions && restrictions['view'].length) {
      return `Only users with ${arrayToEnglish(restrictions['view'])
      } permission can view this issue.`;
    } else if ('edit' in restrictions && restrictions['edit'].length) {
      return `Only users with ${arrayToEnglish(restrictions['edit'])
      } permission may make changes.`;
    } else if ('comment' in restrictions && restrictions['comment'].length) {
      return `Only users with ${arrayToEnglish(restrictions['comment'])
      } permission may comment.`;
    }
    return '';
  }
}

customElements.define(MrRestrictionIndicator.is, MrRestrictionIndicator);
