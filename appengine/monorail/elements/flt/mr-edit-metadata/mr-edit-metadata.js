'use strict';

/**
 * `<mr-edit-metadata>`
 *
 * Editing form for either an approval or the overall issue.
 *
 */
class MrEditMetadata extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-edit-metadata';
  }

  static get properties() {
    return {
      approvalStatus: String,
      approvers: Array,
      setter: Object,
      summary: String,
      cc: Array,
      components: Array,
      fieldList: Array,
      issueStatus: String,
      statuses: Array,
      blockedOn: Array,
      blocking: Array,
      owner: Object,
      labels: Array,
      projectName: {
        type: String,
        statePath: 'projectName',
      },
      isApproval: {
        type: Boolean,
        value: false,
      },
      isApprover: {
        type: Boolean,
        value: false,
      },
      _blockedOnIds: {
        type: Array,
        computed: '_computeBlockerIds(blockedOn, projectName)',
      },
      _blockingIds: {
        type: Array,
        computed: '_computeBlockerIds(blocking, projectName)',
      },
      _labelNames: {
        type: Array,
        computed: '_computeLabelNames(labels)',
      },
      _newCommentText: String,
    };
  }

  reset() {
    this.$.editForm.reset();

    // Since custom elements containing <input> elements have the inputs
    // wrapped in ShadowDOM, those inputs don't get reset with the rest of
    // the form. Haven't been able to figure out a way to replicate form reset
    // behavior with custom input elements.
    Polymer.dom(this.root).querySelector('#approversInput').reset();
  }

  getData() {
    const result = {
      status: this.$.statusInput.value,
      comment: this._newCommentText,
    };
    if (!this.isApproval) {
      result['summary'] = this.$.summaryInput.value;
    } else {
      result['approvers'] = Polymer.dom(this.root).querySelector(
        '#approversInput'
      ).getValue() || [];
    }
    return result;
  }

  _computeIsSelected(a, b) {
    return a === b;
  }

  _computeBlockerIds(arr, projectName) {
    if (!arr || !arr.length) return [];
    return arr.map((v) => {
      if (v.projectName === projectName) {
        return v.localId;
      }
      return `${v.projectName}:${v.localId}`;
    });
  }

  _computeLabelNames(labels) {
    if (!labels) return [];
    return labels.map((l) => {
      return l.label;
    });
  }

  // For simulating && in templating.
  _and(a, b) {
    return a && b;
  }

  // This function exists because <label for="inputId"> doesn't work for custom
  // input elements.
  _clickLabelForCustomInput(e) {
    const target = e.target;
    const forValue = target.getAttribute('for');
    if (forValue) {
      const customInput = Polymer.dom(this.root).querySelector('#' + forValue);
      if (customInput && customInput.focus) {
        customInput.focus();
      }
    }
  }

  _mapUserRefsToNames(users) {
    return users.map((u) => (u.displayName));
  }

  _joinValues(arr) {
    return arr.join(',');
  }
}

customElements.define(MrEditMetadata.is, MrEditMetadata);
