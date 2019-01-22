'use strict';

/**
 * `<mr-edit-metadata>`
 *
 * Editing form for either an approval or the overall issue.
 *
 */
class MrEditMetadata extends MetadataMixin(Polymer.Element) {
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
      hasApproverPrivileges: {
        type: Boolean,
        value: false,
      },
      showNicheFields: {
        type: Boolean,
        value: false,
      },
      disabled: {
        type: Boolean,
        value: false,
      },
      disableAttachments: {
        type: Boolean,
        value: false,
      },
      error: String,
      sendEmail: {
        type: Boolean,
        value: true,
      },
      _statusesGrouped: {
        type: Array,
        computed: '_computeStatusesGrouped(statuses, isApproval)',
      },
      _newAttachments: Array,
      _nicheFieldCount: {
        type: Boolean,
        computed: '_computeNicheFieldCount(fieldDefs)',
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
      if (this.hasApproverPrivileges) {
        const approversInput = Polymer.dom(this.root).querySelector(
          '#approversInput');
        if (approversInput) {
          approversInput.reset();
        }
      }
    }
    Polymer.dom(this.root).querySelectorAll('mr-edit-field').forEach((el) => {
      el.reset();
    });
  }

  save() {
    this.dispatchEvent(new CustomEvent('save'));
  }

  discard() {
    this.dispatchEvent(new CustomEvent('discard'));
  }

  loadAttachments() {
    if (!this._newAttachments || !this._newAttachments.length) return [];
    return this._newAttachments.map((f) => {
      return this._loadLocalFile(f);
    });
  }

  _loadLocalFile(f) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onloadend = () => {
        resolve({filename: f.name, content: btoa(r.result)});
      };
      r.onerror = () => {
        reject(r.error);
      };

      r.readAsBinaryString(f);
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
      if (this.hasApproverPrivileges) {
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

    const fieldDefs = this.fieldDefs || [];
    fieldDefs.forEach((field) => {
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
    if (!users) return [];
    return users.map((u) => (u.displayName));
  }

  _mapComponentRefsToNames(components) {
    if (!components) return [];
    return components.map((c) => c.path);
  }

  _optionsForField(labelDefs, fieldName) {
    const options = [];
    labelDefs = labelDefs || [];

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
    if (!item) return [];
    return [item];
  }

  _sendEmailChecked(evt) {
    this.sendEmail = evt.detail.checked;
  }
}

customElements.define(MrEditMetadata.is, MrEditMetadata);
