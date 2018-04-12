'use strict';

/**
 * `<mr-gates-view>` ....
 *
 * The view for showing and navigating between all gates on a launch issue.
 *
 */
class MrGatesView extends Polymer.Element {
  static get is() {
    return 'mr-gates-view';
  }

  static get properties() {
    return {
      gates: {
        type: Array,
        value: () => {
          return [];
        },
      },
      currentGateIndex: {
        type: Number,
        value: 0,
        notify: true,
        observer: '_gateChanged',
      },
      currentGateName: {
        type: String,
        computed: '_computeCurrentGateName(currentGateIndex)',
      },
      _nextDisabled: {
        type: Boolean,
        computed: '_computeNextDisabled(gates.length, currentGateIndex)',
      },
      _prevDisabled: {
        type: Boolean,
        computed: '_computePrevDisabled(gates.length, currentGateIndex)',
      },
    };
  }

  previous() {
    this.currentGateIndex--;
  }

  next() {
    this.currentGateIndex++;
  }

  _computeCurrentGateName(idx) {
    return this.gates[idx].gateName;
  }

  _computeGateHidden(currentGateIndex, index) {
    return currentGateIndex !== index;
  }

  _computeNextDisabled(gateLength, index) {
    return index >= gateLength - 1;
  }

  _computePrevDisabled(gateLength, index) {
    return index <= 0;
  }
}
customElements.define(MrGatesView.is, MrGatesView);
