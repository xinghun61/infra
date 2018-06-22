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
      },
      fetchingIssue: {
        type: Boolean,
        statePath: 'fetchingIssue',
      },
      fetchIssueError: {
        type: String,
        statePath: 'fetchIssueError',
      },
      phases: Array,
      loginUrl: String,
      logoutUrl: String,
      queryParams: Object,
      route: String,
      routeData: Object,
      token: {
        type: String,
        observer: '_tokenChanged',
      },
      user: String,
      _token: {
        type: String,
        statePath: 'token',
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

  _issueIdChanged(id, projectName) {
    if (!id || !projectName) return;

    this.dispatch({type: actionType.FETCH_ISSUE_START});

    const message = {
      trace: {token: this._token},
      issue_ref: {
        project_name: projectName,
        local_id: id,
      },
    };
    window.prpcClient.call(
      'monorail.Issues', 'GetIssue', message
    ).then((resp) => {
      this.dispatch({
        type: actionType.FETCH_ISSUE_SUCCESS,
        issue: resp.issue,
      });
    }, (error) => {
      this.dispatch({
        type: actionType.FETCH_ISSUE_FAILURE,
        error,
      });
    });
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
