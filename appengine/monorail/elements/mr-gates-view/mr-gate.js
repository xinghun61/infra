'use strict';

/**
 * `<mr-gate>` ....
 *
 * This element displays the view for a single gate on a launch issue.
 *
 */
class MrGate extends Polymer.Element {
  static get is() {
    return 'mr-gate';
  }

  static get properties() {
    return {
      approvals: {
        type: Array,
        value: [],
      },
    };
  }
}
customElements.define(MrGate.is, MrGate);
