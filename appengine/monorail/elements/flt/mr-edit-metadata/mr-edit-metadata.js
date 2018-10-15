'use strict';

/**
 * `<mr-edit-metadata>`
 *
 * Editing form for either an approval or the overall issue.
 *
 */
class MrEditMetadata extends MetadataMixin(ReduxMixin(Polymer.Element)) {
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
      summary: {
        type: String,
        value: '',
      },
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
      ownerName: {
        type: String,
        value: '',
      },
      labelNames: {
        type: Array,
        value: () => [],
      },
      phaseName: String,
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
      _statusesGrouped: {
        type: Array,
        computed: '_computeStatusesGrouped(statuses, isApproval)',
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
    }
    Polymer.dom(this.root).querySelectorAll('mr-edit-field').forEach((el) => {
      el.reset();
    });
  }

  getDelta() {
    const result = {};
    const root = Polymer.dom(this.root);

    const statusInput = root.querySelector('#statusInput');
    if (statusInput) {
      const newStatus = statusInput.value;
      if (newStatus !== this.status) {
        result['status'] = newStatus;
      }
    }

    const commentContent = root.querySelector('#commentText').value;
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

      const summaryInput = root.querySelector('#summaryInput');
      if (summaryInput) {
        const newSummary = summaryInput.value;
        if (newSummary !== this.summary) {
          result['summary'] = newSummary;
        }
      }

      const ownerInput = root.querySelector('#ownerInput');
      if (ownerInput) {
        const newOwner = ownerInput.getValue();
        if (newOwner !== this.ownerName) {
          result['owner'] = newOwner;
        }
      }

      this._addListChangesToDelta(result, 'labelsInput',
        'labelsAdded', 'labelsRemoved');

      this._addListChangesToDelta(result, 'ccInput',
        'ccAdded', 'ccRemoved');

      this._addListChangesToDelta(result, 'componentsInput',
        'componentsAdded', 'componentsRemoved');

      this._addListChangesToDelta(result, 'blockedOnInput',
        'blockedOnAdded', 'blockedOnRemoved');

      this._addListChangesToDelta(result, 'blockingInput',
        'blockingAdded', 'blockingRemoved');
    }

    let fieldValuesAdded = [];
    let fieldValuesRemoved = [];

    this.fieldDefs.forEach((field) => {
      const fieldName = field.fieldRef.fieldName;
      const input = root.querySelector(
        `#${this._idForField(fieldName)}`);
      const valuesAdded = input.getValuesAdded();
      const valuesRemoved = input.getValuesRemoved();

      valuesAdded.forEach((v) => {
        fieldValuesAdded.push({
          fieldRef: {
            fieldName: field.fieldRef.fieldName,
            fieldId: field.fieldRef.fieldId,
          },
          value: v,
        });
      });

      valuesRemoved.forEach((v) => {
        fieldValuesRemoved.push({
          fieldRef: {
            fieldName: field.fieldRef.fieldName,
            fieldId: field.fieldRef.fieldId,
          },
          value: v,
        });
      });
    });

    if (fieldValuesAdded.length) {
      result['fieldValuesAdded'] = fieldValuesAdded;
    }
    if (fieldValuesRemoved.length) {
      result['fieldValuesRemoved'] = fieldValuesRemoved;
    }

    return result;
  }

  toggleNicheFields() {
    this.showNicheFields = !this.showNicheFields;
  }

  _addListChangesToDelta(delta, inputId, addedKey, removedKey) {
    const root = Polymer.dom(this.root);
    const input = root.querySelector(`#${inputId}`);
    if (!input) return;
    const valuesAdded = input.getValuesAdded();
    const valuesRemoved = input.getValuesRemoved();
    if (valuesAdded && valuesAdded.length) {
      delta[addedKey] = valuesAdded;
    }
    if (valuesRemoved && valuesRemoved.length) {
      delta[removedKey] = valuesRemoved;
    }
  }

  _computeNicheFieldCount(fieldDefs) {
    return fieldDefs.reduce((acc, fd) => acc + (fd.isNiche | 0), 0);
  }

  _computeIsSelected(a, b) {
    return a === b;
  }

  _computeStatusesGrouped(statuses, isApproval) {
    if (isApproval) {
      return [{statuses: statuses}];
    }
    return [
      {
        name: 'Open',
        statuses: statuses.filter((s) => s.meansOpen),
      },
      {
        name: 'Closed',
        statuses: statuses.filter((s) => !s.meansOpen),
      },
    ];
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

    // TODO(zhangtiff): Find a way to avoid traversing through every label on
    // every enum field.
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

  _fieldIsHidden(showNicheFields, isNiche) {
    return !showNicheFields && isNiche;
  }

  _wrapList(item) {
    return [item];
  }
}

customElements.define(MrEditMetadata.is, MrEditMetadata);
