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
      email: String,
      loginUrl: String,
      logoutUrl: String,
    };
  }
}

customElements.define(MrHeader.is, MrHeader);
