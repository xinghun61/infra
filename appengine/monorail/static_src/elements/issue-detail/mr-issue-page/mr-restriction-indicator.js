// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {PolymerElement, html} from '@polymer/polymer';

import {connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import * as user from 'elements/reducers/user.js';
import {arrayToEnglish} from 'elements/shared/helpers.js';


/**
 * `<mr-restriction-indicator>`
 *
 * Display for showing whether an issue is restricted.
 *
 */
export class MrRestrictionIndicator extends connectStore(PolymerElement) {
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
        :host([show-notice]) {
          background-color: var(--chops-red-700);
          color: white;
          font-weight: bold;
        }
        :host([show-notice]) i {
          color: white;
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
        i.warning-icon {
          margin-right: 4px;
        }
        i[hidden] {
          display: none;
        }
      </style>
      <i
        class="lock-icon material-icons"
        icon="lock"
        hidden$="[[!_restrictionText]]"
        title$="[[_restrictionText]]"
      >
        lock
      </i>
      <i
        class="warning-icon material-icons"
        icon="warning"
        hidden$="[[!showNotice]]"
        title$="[[_noticeText]]"
    >
        warning
      </i>
      [[_combinedText]]
    `;
  }

  static get is() {
    return 'mr-restriction-indicator';
  }

  static get properties() {
    return {
      restrictions: Object,
      prefs: Object,
      _restrictionText: {
        type: String,
        computed: '_computeRestrictionText(restrictions)',
      },
      _noticeText: {
        type: String,
        computed: '_computeNoticeText(restrictions, prefs)',
      },
      showNotice: {
        type: String,
        reflectToAttribute: true,
        computed: '_computeShowNotice(_noticeText)',
      },
      _combinedText: {
        type: String,
        computed: '_computeCombinedText(_restrictionText, _noticeText)',
      },
      hidden: {
        type: Boolean,
        reflectToAttribute: true,
        computed: '_computeHidden(_combinedText)',
      },
    };
  }

  stateChanged(state) {
    this.setProperties({
      restrictions: issue.restrictions(state),
      prefs: user.user(state).prefs,
    });
  }

  _computeNoticeText(restrictions, prefs) {
    if (!prefs) return '';
    if (!restrictions) return '';
    if ('view' in restrictions && restrictions['view'].length) return '';
    if (prefs.get('public_issue_notice') === 'true') {
      return 'Public issue: Please do not post confidential information.';
    }
    return '';
  }

  _computeShowNotice(_noticeText) {
    return _noticeText != '';
  }

  _computeCombinedText(_restrictionText, _noticeText) {
    if (_noticeText) return _noticeText;
    return _restrictionText;
  }

  _computeHidden(_combinedText) {
    return !_combinedText;
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
