// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../chops/chops-header/chops-header.js';
import './mr-issue-header.js';
import '../mr-issue-details/mr-issue-details.js';
import '../mr-metadata/mr-issue-metadata.js';
import '../mr-launch-overview/mr-launch-overview.js';
import {ReduxMixin, actionType, actionCreator} from '../../redux/redux-mixin.js';

/**
 * `<mr-approval-page>`
 *
 * The main entry point for a given launch issue.
 *
 */
export class MrApprovalPage extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style>
        .container-issue {
          width: 100%;
          flex-direction: column;
          align-items: stretch;
          justify-content: flex-start;
        }
        .container-issue-content {
          padding: 0 16px;
          overflow: hidden;
          flex-grow: 1;
          display: flex;
          align-items: stretch;
          justify-content: space-between;
          flex-direction: row;
          flex-wrap: nowrap;
          box-sizing: border-box;
        }
        .container-outside {
          box-sizing: border-box;
          width: 100%;
          max-width: 100%;
          margin: auto;
          padding: 0;
          display: flex;
          align-items: stretch;
          justify-content: space-between;
          flex-direction: row;
          flex-wrap: no-wrap;
        }
        .main-item {
          flex-grow: 0;
          flex-shrink: 0;
          box-sizing: border-box;
          min-height: 100%;
        }
        .metadata-container {
          font-size: 85%;
          background: var(--monorail-metadata-open-bg);
          border-right: var(--chops-normal-border);
          border-bottom: var(--chops-normal-border);
          width: 17%;
          min-width: 256px;
          flex-grow: 0;
          flex-shrink: 0;
          box-sizing: border-box;
          z-index: 100;
        }
        mr-issue-header {
          z-index: 10;
          position: sticky;
          top: 0;
          margin-bottom: 0.25em;
          width: 100%;
        }
        mr-issue-details {
          padding-right: 16px;
          border-right: var(--chops-normal-border);
          width: 50%;
        }
        mr-issue-metadata {
          position: sticky;
          top: 0.5em;
        }
        mr-launch-overview {
          padding-left: 16px;
          width: 50%;
        }
        @media (max-width: 1024px) {
          .container-issue-content {
            flex-direction: column;
          }
          .main-item {
            width: 100%;
            padding: 0;
            min-height: 0;
            border: 0;
          }
        }
        @media (max-width: 840px) {
          .container-outside {
            flex-direction: column;
          }
          .metadata-container {
            margin: 0.25em 0;
            width: 100%;
            height: auto;
          }
        }
      </style>
      <template is="dom-if" if="[[_showLoading(issueLoaded, fetchIssueError)]]">
        <div class="container-outside">
          Loading...
        </div>
      </template>
      <template is="dom-if" if="[[fetchIssueError]]">
        <div class="container-outside">
          [[fetchIssueError.description]]
        </div>
      </template>
      <template is="dom-if" if="[[issueLoaded]]">
        <div class="container-outside">
          <aside class="metadata-container">
            <mr-issue-metadata></mr-issue-metadata>
          </aside>
          <div class="container-issue">
            <mr-issue-header></mr-issue-header>
            <div class="container-issue-content">
              <mr-issue-details class="main-item"></mr-issue-details>
              <mr-launch-overview class="main-item"></mr-launch-overview>
            </div>
          </div>
        </div>
      </template>
    `;
  }

  static get is() {
    return 'mr-approval-page';
  }

  static get properties() {
    return {
      issue: {
        type: Object,
        observer: '_issueChanged',
      },
      issueId: Number,
      issueLoaded: Boolean,
      projectName: {
        type: String,
        observer: '_projectNameChanged',
      },
      fetchingIssue: Boolean,
      fetchingProjectConfig: Boolean,
      fetchIssueError: String,
      userDisplayName: {
        type: String,
        observer: '_userDisplayNameChanged',
      },
      _user: Object,
    };
  }

  static mapStateToProps(state, element) {
    return {
      issue: state.issue,
      issueId: state.issueId,
      issueLoaded: state.issueLoaded,
      projectName: state.projectName,
      fetchingIssue: state.fetchingIssue,
      fetchingProjectConfig: state.fetchingProjectConfig,
      fetchIssueError: state.fetchIssueError,
      _user: state.user,
    };
  }

  static get observers() {
    return [
      '_issueIdChanged(issueId, projectName)',
    ];
  }

  _issueChanged(issue) {
    document.title =
      `${issue.localId} - ${issue.summary} - ${issue.projectName} - Monorail`;
  }

  _projectNameChanged(projectName) {
    if (!projectName || this.fetchingProjectConfig) return;
    // Reload project config when the project name changes.

    this.dispatchAction({type: actionType.FETCH_PROJECT_CONFIG_START});

    const message = {
      projectName,
    };

    const getConfig = window.prpcClient.call(
      'monorail.Projects', 'GetConfig', message
    );

    // TODO(zhangtiff): Remove this once we properly stub out prpc calls.
    if (!getConfig) return;

    getConfig.then((resp) => {
      this.dispatchAction({
        type: actionType.FETCH_PROJECT_CONFIG_SUCCESS,
        projectConfig: resp,
      });
    }, (error) => {
      this.dispatchAction({
        type: actionType.FETCH_PROJECT_CONFIG_FAILURE,
        error,
      });
    });
  }

  _showLoading(issueLoaded, fetchIssueError) {
    return !issueLoaded && !fetchIssueError;
  }

  _issueIdChanged(id, projectName) {
    if (!id || !projectName || this.fetchingIssue) return;
    // Reload the issue data when the id changes.

    const message = {
      issueRef: {
        projectName: projectName,
        localId: id,
      },
    };

    actionCreator.fetchIssue(this.dispatchAction.bind(this), message);
    actionCreator.fetchComments(this.dispatchAction.bind(this), message);
    actionCreator.fetchIsStarred(this.dispatchAction.bind(this), message);
  }

  _userDisplayNameChanged(userDisplayName) {
    this.dispatchAction({type: actionType.FETCH_USER_START});

    const getUser = window.prpcClient.call(
      'monorail.Users', 'GetUser', {
        userRef: {
          displayName: userDisplayName,
        },
      }
    );

    const getMemberships = window.prpcClient.call(
      'monorail.Users', 'GetMemberships', {
        userRef: {
          displayName: userDisplayName,
        },
      }
    );

    Promise.all([getUser, getMemberships]).then((resp) => {
      this.dispatchAction({
        type: actionType.FETCH_USER_SUCCESS,
        user: resp[0],
        groups: resp[1].groupRefs,
      });
      actionCreator.fetchUserHotlists(this.dispatchAction.bind(this), userDisplayName);
    }, (error) => {
      this.dispatchAction({
        type: actionType.FETCH_USER_FAILURE,
        error,
      });
    });
  }
}

customElements.define(MrApprovalPage.is, MrApprovalPage);
