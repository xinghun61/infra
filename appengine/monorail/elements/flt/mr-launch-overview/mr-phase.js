'use strict';

const TARGET_PHASE_MILESTONE_MAP = {
  'Beta': 'feature_freeze',
  'Stable-Exp': 'final_beta_cut',
  'Stable-Full': 'stable_cut',
};

const APPROVED_PHASE_MILESTONE_MAP = {
  'Beta': 'earliest_beta',
  'Stable-Exp': 'final_beta',
  'Stable-Full': 'stable_date',
};

/**
 * `<mr-phase>`
 *
 * This is the component for a single phase.
 *
 */
class MrPhase extends MetadataMixin(ReduxMixin(Polymer.Element)) {
  static get is() {
    return 'mr-phase';
  }

  static get properties() {
    return {
      projectName: {
        type: String,
        statePath: 'projectName',
      },
      issueId: {
        type: Number,
        statePath: 'issueId',
      },
      phaseName: {
        type: String,
        value: '',
      },
      // Possible values: Target, Approved, Launched
      // TODO(zhangtiff): Compute this dynamically based on some attribute of
      // the phase.
      status: {
        type: String,
        value: 'Target',
      },
      target: {
        type: Number,
        computed: '_computeTarget(fieldValueMap, phaseName)',
      },
      approvals: Array,
      fieldDefs: {
        type: Array,
        statePath: selectors.fieldDefsForPhases,
      },
      fieldValueMap: {
        type: Object,
        statePath: selectors.issueFieldValueMap,
        value: () => {},
      },
      _nextDate: {
        type: Number, // Unix time.
        computed: `_computeNextDate(
          phaseName, status, _milestoneData.mstones)`,
        value: 0,
      },
      _dateDescriptor: {
        type: String,
        computed: '_computeDateDescriptor(status)',
      },
      _setPhaseFields: {
        type: Array,
        computed: '_computeSetPhaseFields(fieldDefs, fieldValueMap, phaseName)',
      },
      _milestoneData: Object,
    };
  }

  edit() {
    this.$.metadataForm.reset();
    this.$.editPhase.open();
  }

  cancel() {
    this.$.editPhase.close();
  }

  save() {
    const data = this.$.metadataForm.getDelta();
    let message = {
      issueRef: {
        projectName: this.projectName,
        localId: this.issueId,
      },
    };
    let delta = {};

    const fieldValuesAdded = data.fieldValuesAdded || [];
    const fieldValuesRemoved = data.fieldValuesRemoved || [];

    if (fieldValuesAdded.length) {
      delta['fieldValsAdd'] = data.fieldValuesAdded.map(
        (fv) => Object.assign({phaseRef: {phaseName: this.phaseName}}, fv));
    }

    if (fieldValuesRemoved.length) {
      delta['fieldValsRemove'] = data.fieldValuesRemoved.map(
        (fv) => Object.assign({phaseRef: {phaseName: this.phaseName}}, fv));
    }

    if (data.comment) {
      message['commentContent'] = data.comment;
    }

    if (Object.keys(delta).length > 0) {
      message.delta = delta;
    }

    if (message.commentContent || message.delta) {
      actionCreator.updateIssue(this.dispatch.bind(this), message);
    }

    this.cancel();
  }

  _computeNextDate(phaseName, status, data) {
    // Data pulled from https://chromepmo.appspot.com/schedule/mstone/json?mstone=xx
    if (!phaseName || !status || !data || !data.length) return 0;

    let key = TARGET_PHASE_MILESTONE_MAP[phaseName];
    if (['Approved', 'Launched'].includes(status)) {
      key = APPROVED_PHASE_MILESTONE_MAP[phaseName];
    }
    if (!key || !(key in data)) return 0;
    return Math.floor((new Date(data[key])).getTime() / 1000);
  }

  _computeDateDescriptor(status) {
    if (status === 'Approved') {
      return 'Launching on ';
    } else if (status === 'Launched') {
      return 'Launched on ';
    }
    return 'Due by ';
  }

  _computeSetPhaseFields(fieldDefs, fieldValueMap, phaseName) {
    if (!fieldDefs || !fieldValueMap) return [];
    return fieldDefs.filter((fd) => fieldValueMap.has(
      this._makeFieldValueMapKey(fd.fieldRef.fieldName, phaseName)
    ));
  }

  _computeTarget(fieldValueMap, phaseName) {
    const targets = this._valuesForField(fieldValueMap, 'M-Target', phaseName);
    return targets.length ? targets[0] : undefined;
  }

  _isEmpty(str) {
    return !str || !str.length;
  }

  _isLastItem(l, i) {
    return i >= l - 1;
  }
}
customElements.define(MrPhase.is, MrPhase);
