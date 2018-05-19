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
      user: {
        type: String,
        value: 'loggedin@chromium.org',
      },
      viewedUser: String,
    };
  }
}

customElements.define(MrProfilePage.is, MrProfilePage);
