'use strict';

const TARGET_GATE_MILESTONE_MAP = {
  'Beta': 'feature_freeze',
  'Stable Exp': 'final_beta_cut',
  'Stable': 'stable_cut',
};

const APPROVED_GATE_MILESTONE_MAP = {
  'Beta': 'earliest_beta',
  'Stable Exp': 'final_beta',
  'Stable': 'stable_date',
};

/**
 * `<mr-gate>`
 *
 * This is the component for a single gate.
 *
 */
class MrGate extends Polymer.Element {
  static get is() {
    return 'mr-gate';
  }

  static get properties() {
    return {
      user: String,
      gate: Object,
      _nextDate: {
        type: Date,
        computed: `_computeNextDate(gate.gateName, gate.status,
          _milestoneData.mstones)`,
      },
      _dateDescriptor: {
        type: String,
        computed: '_computeDateDescriptor(gate.status)',
      },
      _milestoneData: Object,
    };
  }

  _computeNextDate(gateName, status, data) {
    // Data pulled from https://chromepmo.appspot.com/schedule/mstone/json?mstone=67
    if (!gateName || !status || !data || !data.length) return null;
    data = data[0];

    let key = TARGET_GATE_MILESTONE_MAP[gateName];
    if (['Approved', 'Launched'].includes(status)) {
      key = APPROVED_GATE_MILESTONE_MAP[gateName];
    }
    return new Date(data[key]);
  }

  _computeDateDescriptor(status) {
    if (status === 'Approved') {
      return 'Launching on ';
    } else if (status === 'Launched') {
      return 'Launched on ';
    }
    return 'Due by ';
  }
}
customElements.define(MrGate.is, MrGate);
