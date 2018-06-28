'use strict';

const TARGET_PHASE_MILESTONE_MAP = {
  'Beta': 'feature_freeze',
  'Stable Exp': 'final_beta_cut',
  'Stable': 'stable_cut',
};

const APPROVED_PHASE_MILESTONE_MAP = {
  'Beta': 'earliest_beta',
  'Stable Exp': 'final_beta',
  'Stable': 'stable_date',
};

/**
 * `<mr-phase>`
 *
 * This is the component for a single phase.
 *
 */
class MrPhase extends Polymer.Element {
  static get is() {
    return 'mr-phase';
  }

  static get properties() {
    return {
      phaseName: String,
      status: String,
      target: Number,
      approvals: Array,
      _nextDate: {
        type: Date,
        computed: `_computeNextDate(phaseName, status, _milestoneData.mstones)`,
      },
      _dateDescriptor: {
        type: String,
        computed: '_computeDateDescriptor(status)',
      },
      _milestoneData: Object,
    };
  }

  _computeNextDate(phaseName, status, data) {
    // Data pulled from https://chromepmo.appspot.com/schedule/mstone/json?mstone=67
    if (!phaseName || !status || !data || !data.length) return null;
    data = data[0];

    let key = TARGET_PHASE_MILESTONE_MAP[phaseName];
    if (['Approved', 'Launched'].includes(status)) {
      key = APPROVED_PHASE_MILESTONE_MAP[phaseName];
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
customElements.define(MrPhase.is, MrPhase);
