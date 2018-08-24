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
      approvers: {
        type: Array,
        value: () => [],
      },
      setter: {
        type: Object,
        value: () => {},
      },
      summary: String,
      cc: {
        type: Array,
        value: () => [],
      },
      components: {
        type: Array,
        value: () => [],
      },
      fieldDefs: {
        type: Array,
        value: () => [],
      },
      fieldValues: {
        type: Array,
        value: () => [],
      },
      status: String,
      statuses: {
        type: Array,
        value: () => [],
      },
      blockedOn: {
        type: Array,
        value: () => [],
      },
      blocking: {
        type: Array,
        value: () => [],
      },
      ownerName: String,
      labelNames: {
        type: Array,
        value: () => [],
      },
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
      showNicheFields: {
        type: Boolean,
        value: false,
      },
      _nicheFieldCount: {
        type: Boolean,
        computed: '_computeNicheFieldCount(fieldDefs)',
      },
      _fieldValueMap: {
        type: Object,
        statePath: selectors.issueFieldValueMap,
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
      Polymer.dom(this.root).querySelectorAll('mr-edit-field').forEach((el) => {
        el.reset();
      });
    }
  }

  getDelta() {
    const result = {};
    const root = Polymer.dom(this.root);

    const newStatus = this.$.statusInput.value;
    if (newStatus !== this.status) {
      result['status'] = newStatus;
    }

    const commentContent = this.$.commentText.value;
    if (commentContent) {
      result['comment'] = commentContent;
    }

    if (this.isApproval) {
      if (this.isApprover) {
        const approversInput = root.querySelector('#approversInput');
        result['approversAdded'] = approversInput.getValuesAdded();
        result['approversRemoved'] = approversInput.getValuesRemoved();
      }
    } else {
      // TODO(zhangtiff): Consider representing baked-in fields such as owner,
      // cc, and status similarly to custom fields to reduce repeated code.

      const newSummary = root.querySelector('#summaryInput').value;
      if (newSummary !== this.summary) {
        result['summary'] = newSummary;
      }

      // Labels.
      const labelsInput = root.querySelector('#labelsInput');
      result['labelsAdded'] = labelsInput.getValuesAdded();
      result['labelsRemoved'] = labelsInput.getValuesRemoved();

      const newOwner = root.querySelector('#ownerInput').getValue();
      if (newOwner !== this.ownerName) {
        result['owner'] = newOwner;
      }

      const ccInput = root.querySelector('#ccInput');
      result['ccAdded'] = ccInput.getValuesAdded();
      result['ccRemoved'] = ccInput.getValuesRemoved();

      const componentsInput = root.querySelector('#componentsInput');
      result['componentsAdded'] = componentsInput.getValuesAdded();
      result['componentsRemoved'] = componentsInput.getValuesRemoved();

      const blockedOnInput = root.querySelector('#blockedOnInput');
      result['blockedOnAdded'] = blockedOnInput.getValuesAdded();
      result['blockedOnRemoved'] = blockedOnInput.getValuesRemoved();

      const blockingInput = root.querySelector('#blockingInput');
      result['blockingAdded'] = blockingInput.getValuesAdded();
      result['blockingRemoved'] = blockingInput.getValuesRemoved();
    }

    result['fieldValuesAdded'] = [];
    result['fieldValuesRemoved'] = [];

    this.fieldDefs.forEach((field) => {
      const fieldName = field.fieldRef.fieldName;
      const input = root.querySelector(
        `#${this._idForField(fieldName)}`);
      const valuesAdded = input.getValuesAdded();
      const valuesRemoved = input.getValuesRemoved();

      valuesAdded.forEach((v) => {
        result['fieldValuesAdded'].push({
          fieldRef: {
            fieldName: field.fieldRef.fieldName,
          },
          value: v,
        });
      });

      valuesRemoved.forEach((v) => {
        result['fieldValuesRemoved'].push({
          fieldRef: {
            fieldName: field.fieldRef.fieldName,
          },
          value: v,
        });
      });
    });

    return result;
  }

  toggleNicheFields() {
    this.showNicheFields = !this.showNicheFields;
  }

  _computeNicheFieldCount(fieldDefs) {
    return fieldDefs.reduce((acc, fd) => acc + (fd.isNiche | 0), 0);
  }

  _computeIsSelected(a, b) {
    return a === b;
  }

  _mapBlockerRefsToIdStrings(arr, projectName) {
    if (!arr || !arr.length) return [];
    return arr.map((v) => {
      if (v.projectName === projectName) {
        return `${v.localId}`;
      }
      return `${v.projectName}:${v.localId}`;
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

  _idForField(name) {
    return `${name}Input`;
  }

  _mapUserRefsToNames(users) {
    return users.map((u) => (u.displayName));
  }

  _mapComponentRefsToNames(components) {
    return components.map((c) => c.path);
  }

  _optionsForField(labelDefs, fieldName) {
    const options = [];
    for (const label of labelDefs) {
      const labelName = label.label;
      if (labelName.toLowerCase().startsWith(fieldName.toLowerCase())) {
        const opt = Object.assign({}, label, {
          optionName: labelName.substring(fieldName.length + 1),
        });
        options.push(opt);
      }
    }
    return options;
  }

  _valuesForField(fieldValueMap, name) {
    if (!fieldValueMap) return [];
    return fieldValueMap.get(name) || [];
  }

  _fieldIsHidden(showNicheFields, isNiche) {
    return !showNicheFields && isNiche;
  }

  _wrapList(item) {
    return [item];
  }
}

customElements.define(MrEditMetadata.is, MrEditMetadata);
