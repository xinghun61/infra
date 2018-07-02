'use strict';

/**
 * `<mr-edit-metadata>`
 *
 * Editing form for either an approval or the overall issue.
 *
 */
class MrEditMetadata extends Polymer.Element {
  static get is() {
    return 'mr-edit-metadata';
  }

  static get properties() {
    return {
      cc: Array,
      enums: Array,
      projectName: String,
      urls: Array,
      users: Array,
      statuses: Array,
      status: String,
      summary: String,
      blockedOn: Array,
      blocking: Array,
      labels: Array,
      isApproval: {
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

  getData() {
    const result = {
      status: this.$.statusInput.value,
      comment: this._newCommentText,
    };
    if (!this.isApproval) {
      result[summary] = this.$.summaryInput.value;
    }
    return result;
  }

  _valuesForField(fieldName) {
    const input = Polymer.dom(this.root).querySelector(
      '#' + this._idForField(fieldName)
    );
    if (!input) return [];
    return input.value.split(',').map((str) => (str.trim()));
  }

  _idForField(fieldName, choiceName='') {
    return `${(fieldName + choiceName).replace(/\W+/g, '')}Input`;
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

  _joinValues(arr) {
    return arr.join(',');
  }
}

customElements.define(MrEditMetadata.is, MrEditMetadata);
