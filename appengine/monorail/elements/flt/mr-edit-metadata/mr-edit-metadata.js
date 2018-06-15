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
      enums: Array,
      urls: Array,
      users: Array,
      statuses: Array,
      status: String,
      summary: String,
      priority: String,
      priorities: Array,
      blockedOn: Array,
      blocking: Array,
      labels: Array,
      isApproval: {
        type: Boolean,
        value: false,
      },
      _newCommentText: String,
    };
  }

  getData() {
    return {
      urls: this.urls.map((url) => {
        return {
          name: url.name,
          values: this._valuesForField(url.name),
        };
      }),
      users: this.users.map((user) => {
        return {
          name: user.name,
          values: this._valuesForField(user.name),
        };
      }),
      summary: this.$.summaryInput.value,
      status: this.$.statusInput.value,
      priority: this.$.priorityInput.value,
      comment: this._newCommentText,
    };
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

  _joinValues(arr) {
    return arr.join(',');
  }
}

customElements.define(MrEditMetadata.is, MrEditMetadata);
