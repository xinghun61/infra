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
        observer: '_fetchCommentsAndStarState',
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
      },
      fetchingIssue: {
        type: Boolean,
        statePath: 'fetchingIssue',
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

  _issueIdChanged(id, projectName) {
    if (!id || !projectName || this.fetchingIssue) return;

    this.dispatch({type: actionType.FETCH_ISSUE_START});

    const message = {
      trace: {token: this.token},
      issue_ref: {
        project_name: projectName,
        local_id: id,
      },
    };

    const getIssue = window.prpcClient.call(
      'monorail.Issues', 'GetIssue', message
    );

    getIssue.then((resp) => {
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

  // TODO(zhangtiff): Replace this with middleware that fetches comments
  // after specific actions are dispatched.
  _fetchCommentsAndStarState(issue) {
    if (!this.issueLoaded) return;

    // TODO(zhangtiff): Figure out patterns for batching actions in Redux.
    this.dispatch({type: actionType.FETCH_COMMENTS_START});
    this.dispatch({type: actionType.FETCH_IS_STARRED_START});

    const message = {
      trace: {token: this.token},
      issue_ref: {
        project_name: this.projectName,
        local_id: this.issueId,
      },
    };

    const getComments = window.prpcClient.call(
      'monorail.Issues', 'ListComments', message
    );

    const getIsStarred = window.prpcClient.call(
      'monorail.Issues', 'IsIssueStarredRequest', message
    );

    getComments.then((resp) => {
      this.dispatch({
        type: actionType.FETCH_COMMENTS_SUCCESS,
        comments: resp.comments,
      });
    }, (error) => {
      this.dispatch({
        type: actionType.FETCH_COMMENTS_FAILURE,
        error,
      });
    });

    getIsStarred.then((resp) => {
      this.dispatch({
        type: actionType.FETCH_IS_STARRED_SUCCESS,
        isStarred: resp.isStarred,
      });
    }, (error) => {
      this.dispatch({
        type: actionType.FETCH_IS_STARRED_FAILURE,
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
