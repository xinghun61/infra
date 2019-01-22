'use strict';

const TARGET_PHASE_MILESTONE_MAP = {
  'Beta': 'feature_freeze',
  'Stable-Exp': 'final_beta_cut',
  'Stable': 'stable_cut',
  'Stable-Full': 'stable_cut',
};

const APPROVED_PHASE_MILESTONE_MAP = {
  'Beta': 'earliest_beta',
  'Stable-Exp': 'final_beta',
  'Stable': 'stable_date',
  'Stable-Full': 'stable_date',
};

// See monorail:4692 and the use of PHASES_WITH_MILESTONES
// in tracker/issueentry.py
const PHASES_WITH_MILESTONES = ['Beta', 'Stable', 'Stable-Exp', 'Stable-Full'];

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
      issue: {
        type: Object,
        statePath: 'issue',
        observer: 'reset',
      },
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
      updatingIssue: {
        type: Boolean,
        statePath: 'updatingIssue',
        observer: '_updatingIssueChanged',
      },
      updateIssueError: {
        type: Object,
        statePath: 'updateIssueError',
      },
      // Possible values: Target, Approved, Launched.
      _status: {
        type: String,
        computed: `_computeStatus(_targetMilestone, _approvedMilestone,
          _launchedMilestone)`,
      },
      _approvedMilestone: {
        type: Number,
        computed: '_computeApprovedMilestone(fieldValueMap, phaseName)',
      },
      _launchedMilestone: {
        type: Number,
        computed: '_computeLaunchedMilestone(fieldValueMap, phaseName)',
      },
      _targetMilestone: {
        type: Number,
        computed: '_computeTargetMilestone(fieldValueMap, phaseName)',
      },
      _fetchedMilestone: {
        type: Number,
        computed: `_computeFetchedMilestone(_targetMilestone, _approvedMilestone,
          _launchedMilestone)`,
        observer: '_fetchMilestoneData',
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
          phaseName, _status, _milestoneData.mstones)`,
        value: 0,
      },
      _dateDescriptor: {
        type: String,
        computed: '_computeDateDescriptor(_status)',
      },
      _setPhaseFields: {
        type: Array,
        computed: '_computeSetPhaseFields(fieldDefs, fieldValueMap, phaseName)',
      },
      _milestoneData: Object,
    };
  }

  edit() {
    this.reset();
    this.$.editPhase.open();
  }

  cancel() {
    this.$.editPhase.close();
  }

  reset() {
    this.$.metadataForm.reset();
  }

  save() {
    const metadata = this.$.metadataForm;
    const data = metadata.getDelta();
    let message = {
      issueRef: {
        projectName: this.projectName,
        localId: this.issueId,
      },
    };

    if (metadata.sendEmail) {
      message.sendEmail = true;
    }

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
  }

  _updatingIssueChanged(isUpdateInFlight) {
    if (!isUpdateInFlight && !this.updateIssueError) {
      // Close phase edit modal only after request finishes without errors.
      this.cancel();
    }
  }

  _computeNextDate(phaseName, status, data) {
    // Data pulled from https://chromepmo.appspot.com/schedule/mstone/json?mstone=xx
    if (!phaseName || !status || !data || !data.length) return 0;
    data = data[0];

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
    // monorail:4692, remove later
    if (!PHASES_WITH_MILESTONES.includes(phaseName)) return [];
    if (!fieldDefs || !fieldValueMap) return [];
    return fieldDefs.filter((fd) => fieldValueMap.has(
      this._makeFieldValueMapKey(fd.fieldRef.fieldName, phaseName)
    ));
  }

  _computeMilestoneFieldValue(fieldValueMap, phaseName, fieldName) {
    const values = this._valuesForField(fieldValueMap, fieldName, phaseName);
    return values.length ? values[0] : undefined;
  }

  _computeApprovedMilestone(fieldValueMap, phaseName) {
    return this._computeMilestoneFieldValue(fieldValueMap, phaseName,
      'M-Approved');
  }

  _computeLaunchedMilestone(fieldValueMap, phaseName) {
    return this._computeMilestoneFieldValue(fieldValueMap, phaseName,
      'M-Launched');
  }

  _computeTargetMilestone(fieldValueMap, phaseName) {
    return this._computeMilestoneFieldValue(fieldValueMap, phaseName,
      'M-Target');
  }

  _computeStatus(target, approved, launched) {
    if (approved >= target) {
      if (launched >= approved) {
        return 'Launched';
      }
      return 'Approved';
    }
    return 'Target';
  }

  _computeFetchedMilestone(target, approved, launched) {
    return Math.max(target || 0, approved || 0, launched || 0);
  }

  _fetchMilestoneData(milestone) {
    if (!milestone) return;
    // HACK. Eventually we want to create a less bespoke way of getting
    // milestone metadata into Monorail.
    window.fetch(
      `https://chromepmo.appspot.com/schedule/mstone/json?mstone=${milestone}`
    ).then((resp) => resp.json()).then((resp) => {
      this._milestoneData = resp;
    });
  }

  _isEmpty(str) {
    return !str || !str.length;
  }

  _isLastItem(l, i) {
    return i >= l - 1;
  }
}
customElements.define(MrPhase.is, MrPhase);
