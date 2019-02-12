// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../mr-flipper.js';
import '../../chops/chops-timestamp/chops-timestamp.js';
import {ReduxMixin} from '../../redux/redux-mixin.js';
import '../../mr-user-link/mr-user-link.js';
/**
 * `<mr-issue-header>`
 *
 * The header for a given launch issue.
 *
 */
export class MrIssueHeader extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style>
        :host {
          width: 100%;
          margin-top: 0;
          font-size: 18px;
          background-color: var(--monorail-metadata-open-bg);
          border-bottom: var(--chops-normal-border);
          font-weight: normal;
          padding: 0.25em 16px;
          box-sizing: border-box;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }
        h1 {
          font-size: 100%;
          line-height: 140%;
          font-weight: normal;
          padding: 0;
          margin: 0;
        }
        mr-flipper {
          font-size: 0.75em;
        }
        .byline {
          display: block;
          font-size: 12px;
          width: 100%;
          line-height: 140%;
          color: hsl(227, 15%, 35%);
        }
        @media (max-width: 840px) {
          :host {
            flex-wrap: wrap;
            justify-content: center;
          }
          .main-text {
            width: 100%;
            margin-bottom: 0.5em;
          }
        }
      </style>
      <div class="main-text">
        <h1>Issue [[issue.localId]]: [[issue.summary]]</h1>
        <small class="byline">
          Created by
          <mr-user-link display-name="[[issue.reporterRef.displayName]]" user-id="[[issue.reporterRef.userId]]"></mr-user-link>
          on <chops-timestamp timestamp="[[issue.openedTimestamp]]"></chops-timestamp>
        </small>
      </div>
      <mr-flipper></mr-flipper>
    `;
  }

  static get is() {
    return 'mr-issue-header';
  }

  static get properties() {
    return {
      created: {
        type: Object,
        value: () => {
          return new Date();
        },
      },
      issue: {
        type: Object,
        value: () => {},
      },
      _flipperCount: {
        type: Number,
        value: 20,
      },
      _flipperIndex: {
        type: Number,
        computed: '_computeFlipperIndex(issue.localId, _flipperCount)',
      },
      _nextId: {
        type: Number,
        computed: '_computeNextId(issue.localId)',
      },
      _prevId: {
        type: Number,
        computed: '_computePrevId(issue.localId)',
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      issue: state.issue,
    };
  }

  _computeFlipperIndex(i, count) {
    return i % count + 1;
  }

  _computeNextId(id) {
    return id + 1;
  }

  _computePrevId(id) {
    return id - 1;
  }
}

customElements.define(MrIssueHeader.is, MrIssueHeader);
