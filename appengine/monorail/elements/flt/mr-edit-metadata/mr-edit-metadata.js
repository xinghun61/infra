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
      approvers: Array,
      setter: Object,
      summary: String,
      cc: Array,
      components: Array,
      fieldDefs: Array,
      fieldValues: Array,
      status: String,
      statuses: Array,
      blockedOn: Array,
      blocking: Array,
      owner: Object,
      labelNames: Array,
      projectConfig: {
        type: String,
        statePath: 'projectConfig',
      },
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
      _fieldValueMap: {
        type: Object,
        computed: '_computeFieldValueMap(fieldValues)',
        value: () => {},
      },
    };
  }

  reset() {
    this.$.editForm.reset();

    // Since custom elements containing <input> elements have the inputs
    // wrapped in ShadowDOM, those inputs don't get reset with the rest of
    // the form. Haven't been able to figure out a way to replicate form reset
    // behavior with custom input elements.
    if (this.isApproval) {
      if (this.isApprover) {
        Polymer.dom(this.root).querySelector('#approversInput').reset();
      }
    } else {
      Polymer.dom(this.root).querySelector('#ownerInput').reset();
      Polymer.dom(this.root).querySelector('#ccInput').reset();
      Polymer.dom(this.root).querySelector('#blockingInput').reset();
      Polymer.dom(this.root).querySelector('#blockedOnInput').reset();
      Polymer.dom(this.root).querySelector('#labelsInput').reset();
    }
  }

  getData() {
    const result = {
      status: this.$.statusInput.value,
      comment: this.$.commentText.value,
    };
    const root = Polymer.dom(this.root);
    if (this.isApproval) {
      if (this.isApprover) {
        result['approvers'] = root.querySelector('#approversInput').getValue();
      }
    } else {
      result['summary'] = root.querySelector('#summaryInput').value;
      result['labels'] = root.querySelector('#labelsInput').getValue();
      result['blockedOn'] = root.querySelector('#blockedOnInput').getValue();
      result['blocking'] = root.querySelector('#blockingInput').getValue();
      result['owner'] = root.querySelector('#ownerInput').getValue();
      result['cc'] = root.querySelector('#ccInput').getValue();
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

  _computeFieldValueMap(fields) {
    return computeFunction.computeFieldValueMap(fields);
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

  _idForField(name) {
    return `${name}Input`;
  }

  _mapUserRefsToNames(users) {
    return users.map((u) => (u.displayName));
  }

  _optionsForField(labelDefs, name) {
    return computeFunction.computeOptionsForField(labelDefs, name);
  }

  _valuesForField(fieldValueMap, name) {
    if (!(name in fieldValueMap)) return [];
    return fieldValueMap[name];
  }

  _statusIsHidden(status, statusDef) {
    return !statusDef.rank && statusDef.status !== status;
  }
}

customElements.define(MrEditMetadata.is, MrEditMetadata);
