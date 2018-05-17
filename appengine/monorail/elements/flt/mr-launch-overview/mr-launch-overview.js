'use strict';

/**
 * `<mr-launch-overview>`
 *
 * This is a shorthand view of the gates for a user to see a quick overview.
 *
 */
class MrLaunchOverview extends Polymer.Element {
  static get is() {
    return 'mr-launch-overview';
  }

  static get properties() {
    return {
      user: String,
      gates: {
        type: Array,
        value: [],
      },
    };
  }
}
customElements.define(MrLaunchOverview.is, MrLaunchOverview);
