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
      loginUrl: String,
      logoutUrl: String,
      queryParams: Object,
      route: String,
      routeData: Object,
      user: {
        type: String,
        observer: '_userChanged',
      },
      _user: {
        type: Object,
        statePath: 'user',
      },
      _userMenuItems: {
        type: Array,
        computed: '_computeUserMenuItems(_user.email, loginUrl, logoutUrl)',
      },
    };
  }

  static get observers() {
    return [
      '_issueIdChanged(issueId, projectName)',
      '_routeChanged(routeData, queryParams)',
    ];
  }

  _projectNameChanged(projectName) {
    if (!projectName || this.fetchingProjectConfig) return;
    // Reload project config when the project name changes.

    this.dispatch({type: actionType.FETCH_PROJECT_CONFIG_START});

    const message = {
      projectName,
    };

    const getConfig = window.prpcClient.call(
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

  _issueIdChanged(id, projectName) {
    if (!id || !projectName || this.fetchingIssue) return;
    // Reload the issue data when the id changes.

    const message = {
      issue_ref: {
        project_name: projectName,
        local_id: id,
      },
    };

    actionCreator.fetchIssue(this.dispatch.bind(this), message);
    actionCreator.fetchComments(this.dispatch.bind(this), message);
    actionCreator.fetchIsStarred(this.dispatch.bind(this), message);
  }

  _routeChanged(routeData, queryParams) {
    this.dispatch({
      type: actionType.UPDATE_ISSUE_REF,
      issueId: Number.parseInt(queryParams.id),
      projectName: routeData.project,
    });
  }

  _userChanged(user) {
    this.dispatch({type: actionType.FETCH_USER_START});

    const getUser = window.prpcClient.call(
      'monorail.Users', 'GetUser', {
        userRef: {
          displayName: user,
        },
      }
    );

    const getMemberships = window.prpcClient.call(
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
    }, (error) => {
      this.dispatch({
        type: actionType.FETCH_USER_FAILURE,
        error,
      });
    });
  }

  _computeUserMenuItems(userEmail, loginUrl, logoutUrl) {
    return [
      {text: 'Switch accounts', url: loginUrl},
      {separator: true},
      {text: 'Profile', url: `/u/${userEmail}`},
      {text: 'Updates', url: `/u/${userEmail}/updates`},
      {text: 'Settings', url: '/hosting/settings'},
      {text: 'Saved queries', url: `/u/${userEmail}/queries`},
      {text: 'Hotlists', url: `/u/${userEmail}/hotlists`},
      {separator: true},
      {text: 'Sign out', url: logoutUrl},
    ];
  }
}

customElements.define(MrApprovalPage.is, MrApprovalPage);
