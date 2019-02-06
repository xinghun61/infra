// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '../../../node_modules/@polymer/polymer/polymer-legacy.js';
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
        .container-main {
          overflow: hidden;
          flex-grow: 1;
          display: flex;
          align-items: stretch;
          justify-content: space-between;
          flex-direction: row;
          flex-wrap: no-wrap;
          box-sizing: border-box;
        }
        .container-outside {
          box-sizing: border-box;
          width: 100%;
          max-width: 100%;
          margin: auto;
          padding: 0.75em 8px;
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
          background: hsl(120, 35%, 95%);
          border: 1px solid hsl(120, 15%, 90%);
          width: 17%;
          min-width: 256px;
          flex-grow: 0;
          flex-shrink: 0;
          margin-right: 16px;
          box-sizing: border-box;
          z-index: 999;
        }
        mr-issue-details {
          padding-right: 16px;
          border-right: 1px dotted hsl(227, 10%, 87%);
          width: 50%;
        }
        mr-launch-overview {
          padding-left: 16px;
          width: 50%;
        }
        @media (max-width: 1280px) {
          .container-outside {
            padding: 0.5em 8px;
          }
          .container-main {
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
        <mr-issue-header></mr-issue-header>
        <div class="container-outside">
          <aside class="metadata-container">
            <mr-issue-metadata></mr-issue-metadata>
          </aside>
          <div class="container-main">
            <mr-issue-details class="main-item"></mr-issue-details>
            <mr-launch-overview class="main-item"></mr-launch-overview>
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
      issue: Object,
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

  _projectNameChanged(projectName) {
    if (!projectName || this.fetchingProjectConfig) return;
    // Reload project config when the project name changes.

    this.dispatchAction({type: actionType.FETCH_PROJECT_CONFIG_START});

    const message = {
      projectName,
    };

    const getConfig = window.prpcCall(
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

    const getUser = window.prpcCall(
      'monorail.Users', 'GetUser', {
        userRef: {
          displayName: userDisplayName,
        },
      }
    );

    const getMemberships = window.prpcCall(
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
