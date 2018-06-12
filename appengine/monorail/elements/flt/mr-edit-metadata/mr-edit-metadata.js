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
      isApprover: Boolean,
      urls: Array,
      users: Array,
      statuses: Array,
      status: String,
      _newCommentText: String,
      _statuses: {
        type: Array,
        computed: '_filterStatuses(status, statuses, isApprover)',
      },
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
      status: this.$.statusInput.value,
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

  _idForField(fieldName) {
    return `${fieldName.replace(/\W+/g, '')}Input`;
  }

  _computeIsSelected(a, b) {
    return a === b;
  }

  _joinValues(arr) {
    return arr.join(',');
  }

  _filterStatuses(status, statuses, isApprover) {
    return statuses.filter((s) => {
      // These statuses should only be set by approvers.
      if (!isApprover && ['NA', 'Approved', 'NotApproved'].includes(s)) {
        return false;
      }
      return s === status || s !== 'NotSet';
    });
  }
}

customElements.define(MrEditMetadata.is, MrEditMetadata);
