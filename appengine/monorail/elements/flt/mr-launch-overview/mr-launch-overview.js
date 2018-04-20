'use strict';

/**
 * `<mr-launch-overview>` ....
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
      gates: {
        type: Array,
        value: [],
      },
    };
  }

  _handleGateFocus(e) {
    let idx = e.target.getAttribute('value') * 1;
    this.dispatchEvent(
      new CustomEvent('gate-selected', {detail: {gateIndex: idx}}));
  }
}
customElements.define(MrLaunchOverview.is, MrLaunchOverview);
