'use strict';

/**
 * `<mr-approval-page>`
 *
 * The main entry point for a given launch issue.
 *
 */
class MrApprovalPage extends Polymer.Element {
  static get is() {
    return 'mr-approval-page';
  }

  static get properties() {
    return {
      summary: String,
      issueId: {
        type: Number,
        computed: '_computeIssueId(queryParams.id)',
      },
      gates: Array,
      loginUrl: String,
      logoutUrl: String,
      queryParams: Object,
      user: String,
      _user: {
        type: String,
        computed: '_computeUser(user, queryParams.you)',
      },
      _userMenuItems: {
        type: Array,
        computed: '_computeUserMenuItems(_user, loginUrl, logoutUrl)',
      },
    };
  }

  _computeIssueId(id) {
    return id * 1;
  }

  // TODO(zhangtiff): Remove the "you" feature once we have real authentication.
  _computeUser(user, you) {
    if (!you) return user;
    return `${you}@chromium.org`;
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
