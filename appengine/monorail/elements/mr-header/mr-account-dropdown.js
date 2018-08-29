'use strict';

/**
 * `<mr-account-dropdown>`
 *
 * The account dropdown in the top right of the page.
 *
 */
class MrAccountDropdown extends Polymer.Element {
  static get is() {
    return 'mr-account-dropdown';
  }

  static get properties() {
    return {
      email: String,
      loginUrl: String,
      logoutUrl: String,
      _menuItems: {
        type: Array,
        computed: '_computeMenuItems(email, loginUrl, logoutUrl)',
      },
    };
  }

  _computeMenuItems(email, loginUrl, logoutUrl) {
    return [
      {text: 'Switch accounts', url: loginUrl},
      {separator: true},
      {text: 'Profile', url: `/u/${email}`},
      {text: 'Updates', url: `/u/${email}/updates`},
      {text: 'Settings', url: '/hosting/settings'},
      {text: 'Saved queries', url: `/u/${email}/queries`},
      {text: 'Hotlists', url: `/u/${email}/hotlists`},
      {separator: true},
      {text: 'Sign out', url: logoutUrl},
    ];
  }
}

customElements.define(MrAccountDropdown.is, MrAccountDropdown);
