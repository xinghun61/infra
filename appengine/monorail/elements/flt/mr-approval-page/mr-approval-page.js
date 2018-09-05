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
      token: {
        type: String,
        observer: '_tokenChanged',
      },
      token: {
        type: String,
        observer: '_tokenChanged',
      },
      tokenExpiresSec: {
        type: Number,
        observer: '_tokenExpiresSecChanged',
      },
      user: {
        type: String,
        observer: '_userChanged',
      },
      _user: {
        type: String,
        statePath: 'user',
      },
      _userMenuItems: {
        type: Array,
        computed: '_computeUserMenuItems(_user, loginUrl, logoutUrl)',
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

    const getConfig = window.__prpc.call(
      'monorail.Projects', 'GetConfig', message, this.token,
      this.tokenExpiresSec
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

    actionCreator.fetchIssue(
        this.dispatch.bind(this), message, this.token, this.tokenExpiresSec);
    actionCreator.fetchComments(
        this.dispatch.bind(this), message, this.token, this.tokenExpiresSec);
    actionCreator.fetchIsStarred(
        this.dispatch.bind(this), message, this.token, this.tokenExpiresSec);
  }

  _routeChanged(routeData, queryParams) {
    this.dispatch({
      type: actionType.UPDATE_ISSUE_REF,
      issueId: Number.parseInt(queryParams.id),
      projectName: routeData.project,
    });
  }

  _tokenChanged(token) {
    this.dispatch({
      type: actionType.UPDATE_TOKEN,
      token,
    });
  }

  _tokenExpiresSecChanged(tokenExpiresSec) {
    this.dispatch({
      type: actionType.UPDATE_TOKEN_EXPIRES_SEC,
      tokenExpiresSec,
    });
  }

  _userChanged(user) {
    this.dispatch({
      type: actionType.UPDATE_USER,
      user,
    });
  }

  _computeUserMenuItems(user, loginUrl, logoutUrl) {
    return [
      {text: 'Switch accounts', url: loginUrl},
      {separator: true},
      {text: 'Profile', url: `/u/${user}`},
      {text: 'Updates', url: `/u/${user}/updates`},
      {text: 'Settings', url: '/hosting/settings'},
      {text: 'Saved queries', url: `/u/${user}/queries`},
      {text: 'Hotlists', url: `/u/${user}/hotlists`},
      {separator: true},
      {text: 'Sign out', url: logoutUrl},
    ];
  }
}

customElements.define(MrApprovalPage.is, MrApprovalPage);
