'use strict';

/**
 * `<mr-launch-overview>`
 *
 * This is a shorthand view of the phases for a user to see a quick overview.
 *
 */
class MrLaunchOverview extends Polymer.Element {
  static get is() {
    return 'mr-launch-overview';
  }

  static get properties() {
    return {
      user: String,
      phases: {
        type: Array,
        value: [],
      },
    };
  }
}
customElements.define(MrLaunchOverview.is, MrLaunchOverview);
