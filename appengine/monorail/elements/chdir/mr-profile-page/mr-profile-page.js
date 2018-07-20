'use strict';

/**
 * `<mr-profile-page>`
 *
 * The main entry point for a Monorail Polymer profile.
 *
 */
class MrProfilePage extends Polymer.Element {
  static get is() {
    return 'mr-profile-page';
  }

  static get properties() {
    return {
      user: String,
      logoutUrl: String,
      loginUrl: String,
      viewedUser: String,
      token: String,
    };
  }
}

customElements.define(MrProfilePage.is, MrProfilePage);
