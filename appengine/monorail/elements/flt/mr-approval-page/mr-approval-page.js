// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * `<mr-approval-page>`
 *
 * The main entry point for a given launch issue.
 *
 */
class MrApprovalPage extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-approval-page';
  }

  static get properties() {
    return {
      issue: {
        type: Object,
        statePath: 'issue',
      },
      issueId: {
        type: Number,
        statePath: 'issueId',
      },
      issueLoaded: {
        type: Boolean,
        statePath: 'issueLoaded',
      },
      projectName: {
        type: String,
        statePath: 'projectName',
        observer: '_projectNameChanged',
      },
      fetchingIssue: {
        type: Boolean,
        statePath: 'fetchingIssue',
      },
      fetchingProjectConfig: {
        type: Boolean,
        statePath: 'fetchingProjectConfig',
      },
      fetchIssueError: {
        type: String,
        statePath: 'fetchIssueError',
      },
      user: {
        type: String,
        observer: '_userChanged',
      },
      _user: {
        type: Object,
        statePath: 'user',
      },
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

    this.dispatch({type: actionType.FETCH_PROJECT_CONFIG_START});

    const message = {
      projectName,
    };

    const getConfig = window.prpcCall(
      'monorail.Projects', 'GetConfig', message
    );

    getConfig.then((resp) => {
      this.dispatch({
        type: actionType.FETCH_PROJECT_CONFIG_SUCCESS,
        projectConfig: resp,
      });
    }, (error) => {
      this.dispatch({
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

    actionCreator.fetchIssue(this.dispatch.bind(this), message);
    actionCreator.fetchComments(this.dispatch.bind(this), message);
    actionCreator.fetchIsStarred(this.dispatch.bind(this), message);
  }

  _userChanged(user) {
    this.dispatch({type: actionType.FETCH_USER_START});

    const getUser = window.prpcCall(
      'monorail.Users', 'GetUser', {
        userRef: {
          displayName: user,
        },
      }
    );

    const getMemberships = window.prpcCall(
      'monorail.Users', 'GetMemberships', {
        userRef: {
          displayName: user,
        },
      }
    );

    Promise.all([getUser, getMemberships]).then((resp) => {
      this.dispatch({
        type: actionType.FETCH_USER_SUCCESS,
        user: resp[0],
        groups: resp[1].groupRefs,
      });
      actionCreator.fetchUserHotlists(this.dispatch.bind(this), user);
    }, (error) => {
      this.dispatch({
        type: actionType.FETCH_USER_FAILURE,
        error,
      });
    });
  }
}

customElements.define(MrApprovalPage.is, MrApprovalPage);
