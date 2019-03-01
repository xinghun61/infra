// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../mr-flipper.js';
import '../../chops/chops-dialog/chops-dialog.js';
import '../../chops/chops-timestamp/chops-timestamp.js';
import {ReduxMixin, actionCreator} from '../../redux/redux-mixin.js';
import '../../mr-user-link/mr-user-link.js';
import '../../mr-code-font-toggle/mr-code-font-toggle.js';
import '../../mr-dropdown/mr-dropdown.js';


const DELETE_ISSUE_CONFIRMATION_NOTICE = `\
Normally, you would just close issues by setting their status to a closed value.
Are you sure you want to delete this issue?`;


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
          justify-content: flex-end;
          align-items: center;
        }
        h1 {
          font-size: 100%;
          line-height: 140%;
          font-weight: normal;
          padding: 0;
          margin: 0;
        }
        .issue-actions {
          min-width: fit-content;
          margin: 3px;
          font-size: 0.75em;
          display: flex;
          flex-direction: column;
          align-items: center;
        }
        .issue-actions a {
          color: var(--chops-link-color);
          cursor: pointer;
        }
        .issue-actions a:hover {
          text-decoration: underline;
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
        .main-text {
          flex-basis: 100%;
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
          <mr-user-link
            display-name="[[issue.reporterRef.displayName]]"
            user-id="[[issue.reporterRef.userId]]"
          ></mr-user-link>
          on <chops-timestamp timestamp="[[issue.openedTimestamp]]"></chops-timestamp>
        </small>
      </div>
      <div class="issue-actions">
        <mr-code-font-toggle
          user-display-name="[[userDisplayName]]"
        ></mr-code-font-toggle>
        <a on-click="_openEditDescription">Edit description</a>
      </div>

      <template is="dom-if" if="[[_issueOptions.length]]">
        <mr-dropdown
          items="[[_issueOptions]]"
          icon="more_vert"
        ></mr-dropdown>
      </template>
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
      userDisplayName: String,
      issue: {
        type: Object,
        value: () => {},
      },
      issuePermissions: Object,
      _issueOptions: {
        type: Array,
        computed: '_computeIssueOptions(issuePermissions)',
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
      issuePermissions: state.issuePermissions,
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

  _computeIssueOptions(issuePermissions) {
    const options = [];
    if ((issuePermissions || []).includes('deleteissue')) {
      options.push({
        text: 'Delete issue',
        handler: this._deleteIssue.bind(this),
      });
    }
    return options;
  }

  _deleteIssue() {
    const ok = confirm(DELETE_ISSUE_CONFIRMATION_NOTICE);
    if (ok) {
      window.prpcClient.call('monorail.Issues', 'DeleteIssue', {
        issueRef: {
          projectName: this.issue.projectName,
          localId: this.issue.localId,
        },
        delete: true,
      }).then(() => {
        const message = {
          issueRef: {
            projectName: this.issue.projectName,
            localId: this.issue.localId,
          },
        };
        actionCreator.fetchIssue(this.dispatchAction.bind(this), message);
      });
    }
  }

  _openEditDescription() {
    this.dispatchEvent(new CustomEvent('open-dialog', {
      bubbles: true,
      composed: true,
      detail: {
        dialogId: 'edit-description',
        fieldName: '',
      },
    }));
  }
}

customElements.define(MrIssueHeader.is, MrIssueHeader);
