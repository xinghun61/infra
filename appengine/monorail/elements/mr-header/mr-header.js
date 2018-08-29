'use strict';

/**
 * `<mr-header>`
 *
 * The main entry point for a given launch issue.
 *
 */
class MrHeader extends Polymer.Element {
  static get is() {
    return 'mr-header';
  }

  static get properties() {
    return {
      loginUrl: String,
      logoutUrl: String,
      user: String,
      _userMenuItems: {
        type: Array,
        computed: '_computeUserMenuItems(user, loginUrl, logoutUrl)',
      },
    };
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

customElements.define(MrHeader.is, MrHeader);
