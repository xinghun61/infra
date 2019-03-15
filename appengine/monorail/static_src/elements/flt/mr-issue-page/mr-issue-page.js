// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../chops/chops-button/chops-button.js';
import '../../chops/chops-header/chops-header.js';
import './mr-issue-header.js';
import '../mr-issue-details/mr-issue-details.js';
import '../mr-metadata/mr-issue-metadata.js';
import '../mr-launch-overview/mr-launch-overview.js';
import {ReduxMixin, actionType, actionCreator} from '../../redux/redux-mixin.js';
import * as user from '../../redux/user.js';
import '../shared/mr-flt-styles.js';
import '../mr-edit-description/mr-edit-description.js';
import './mr-move-copy-issue.js';

/**
 * `<mr-issue-page>`
 *
 * The main entry point for a Monorail issue detail page.
 *
 */
export class MrIssuePage extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style include="mr-flt-styles">
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
        .container-deleted {
          padding: 16px;
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
          top: var(--monorail-header-height);
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
          top: var(--monorail-header-height);
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
            width: 100%;
            height: auto;
            border: 0;
            border-bottom: var(--chops-normal-border);
          }
          mr-issue-metadata, mr-issue-header {
            position: static;
          }
        }
      </style>
      <mr-edit-description id='edit-description'></mr-edit-description>
      <mr-move-copy-issue id='move-copy-issue'></mr-move-copy-issue>

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
      <template is="dom-if" if="[[_isDeleted(issueLoaded, issue)]]">
        <div class="container-deleted">
          <p>Issue [[issueId]] has been deleted.</p>
          <template is="dom-if" if="[[_showUndelete(issuePermissions)]]">
            <chops-button on-click="_undeleteIssue" class="emphasized">
              Undelete Issue
            </chops-button>
          </template>
        </div>
      </template>
      <template is="dom-if" if="[[_showIssue(issueLoaded, issue)]]">
        <div
          class="container-outside"
          on-open-dialog="_onOpenDialog"
        >
          <aside class="metadata-container">
            <mr-issue-metadata></mr-issue-metadata>
          </aside>
          <div class="container-issue">
            <mr-issue-header
              user-display-name="[[userDisplayName]]"
            ></mr-issue-header>
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
    return 'mr-issue-page';
  }

  static get properties() {
    return {
      issue: Object,
      issueId: Number,
      issueLoaded: Boolean,
      issuePermissions: Object,
      projectName: {
        type: String,
        observer: '_projectNameChanged',
      },
      fetchingIssue: Boolean,
      fetchingProjectConfig: Boolean,
      fetchIssueError: String,
      queryParams: {
        type: Object,
        value: () => {},
      },
      issueEntryUrl: String,
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
      issuePermissions: state.issuePermissions,
      projectName: state.projectName,
      fetchingIssue: state.requests.fetchIssue.requesting,
      fetchingProjectConfig: state.requests.fetchProjectConfig.requesting,
      fetchIssueError: state.requests.fetchIssue.error,
      _user: user.currentUser(state),
    };
  }

  static get observers() {
    return [
      '_fetchIssue(issueId, projectName)',
      '_issueChanged(issueId, projectName, issue)',
    ];
  }

  _onOpenDialog(e) {
    this.shadowRoot.querySelector('#' + e.detail.dialogId).open(e);
  }

  _issueChanged(issueId, projectName, issue) {
    let title = issueId ? `${issueId} - ` : 'Loading issue... - ';
    if (issue.isDeleted) {
      title += 'Issue has been deleted - ';
    } else if (issue.summary) {
      title += `${issue.summary} - `;
    }
    if (projectName) {
      title += `${projectName} - `;
    }
    title += 'Monorail';
    document.title = title;
  }

  _projectNameChanged(projectName) {
    if (!projectName || this.fetchingProjectConfig) return;
    // Reload project config and templates when the project name changes.

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

    this.dispatchAction({type: actionType.FETCH_PROJECT_TEMPLATES_START});

    const listTemplates = window.prpcClient.call(
      'monorail.Projects', 'ListProjectTemplates', message
    );

    // TODO(zhangtiff): Remove (see above TODO).
    if (!listTemplates) return;

    listTemplates.then((resp) => {
      this.dispatchAction({
        type: actionType.FETCH_PROJECT_TEMPLATES_SUCCESS,
        projectTemplates: resp,
      });
    }, (error) => {
      this.dispatchAction({
        type: actionType.FETCH_PROJECT_TEMPLATES_FAILURE,
        error,
      });
    });
  }

  _showLoading(issueLoaded, fetchIssueError) {
    return !issueLoaded && !fetchIssueError;
  }

  _fetchIssue(id, projectName) {
    if (!id || !projectName || this.fetchingIssue) return;
    // Reload the issue data when the id changes.

    const message = {
      issueRef: {
        projectName: projectName,
        localId: id,
      },
    };

    this.dispatchAction(actionCreator.fetchIssue(message));
    this.dispatchAction(actionCreator.fetchComments(message));
    this.dispatchAction(actionCreator.fetchIsStarred(message));
  }

  _userDisplayNameChanged(userDisplayName) {
    this.dispatchAction(user.fetch(userDisplayName));
  }

  _undeleteIssue() {
    window.prpcClient.call('monorail.Issues', 'DeleteIssue', {
      issueRef: {
        localId: this.issueId,
        projectName: this.projectName,
      },
      delete: false,
    }).then(() => {
      this._fetchIssue(this.issueId, this.projectName);
    });
  }

  _showUndelete(issuePermissions) {
    return (issuePermissions || []).includes('deleteissue');
  }

  _showIssue(issueLoaded, issue) {
    return issueLoaded && !issue.isDeleted;
  }

  _isDeleted(issueLoaded, issue) {
    return issueLoaded && issue.isDeleted;
  }
}

customElements.define(MrIssuePage.is, MrIssuePage);
