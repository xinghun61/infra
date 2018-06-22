'use strict';

/**
 * `<mr-user-link>`
 *
 * Displays a link to a user profile.
 *
 */
class MrUserLink extends Polymer.Element {
  static get is() {
    return 'mr-user-link';
  }

  static get properties() {
    return {
      displayName: String,
      userId: String,
    };
  }
}
customElements.define(MrUserLink.is, MrUserLink);
