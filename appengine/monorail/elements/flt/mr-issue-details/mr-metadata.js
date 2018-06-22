'use strict';

/**
 * `<mr-metadata>`
 *
 * The metadata view for a single issue. Contains information such as the owner.
 *
 */
class MrMetadata extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-metadata';
  }

  static get properties() {
    return {
      issue: {
        type: Object,
        statePath: 'issue',
      },
      statuses: {
        type: Array,
        value: [
          'Unconfirmed',
          'Untriaged',
          'Available',
          'Assigned',
          'Started',
        ],
      },
      // issue.fieldValues is an array with one entry per values.
      // We want to remap each fieldRef into its own list entry.
      _fieldList: {
        type: Array,
        computed: '_computeFieldList(issue.fieldValues)',
      },
    };
  }

  edit() {
    this.$.editMetadata.open();
  }

  cancel() {
    this.$.editMetadata.close();
  }

  _computeFieldList(values) {
    if (!values) return [];
    const fieldMap = values.reduce((acc, v) => {
      const fieldName = v.fieldRef.fieldName;
      if (!(fieldName in acc)) {
        acc[fieldName] = {
          values: [v.value],
          fieldRef: v.fieldRef,
        };
      } else {
        acc[fieldName].values.push(v.value);
      }
      return acc;
    }, {});

    return Object.keys(fieldMap).map((field) => (fieldMap[field]));
  }

  _fieldIsDate(type) {
    return type === 'DATE_TYPE';
  }

  _fieldIsEnum(type) {
    return type === 'ENUM_TYPE';
  }

  _fieldIsInt(type) {
    return type === 'INT_TYPE';
  }

  _fieldIsStr(type) {
    return type === 'STR_TYPE';
  }

  _fieldIsUser(type) {
    return type === 'USER_TYPE';
  }

  _fieldIsUrl(type) {
    return type === 'URL_TYPE';
  }

  _fieldIsRemainingTypes(type) {
    return this._fieldIsDate(type) || this._fieldIsEnum(type) ||
      this._fieldIsInt(type) || this._fieldIsStr(type);
  }

  _isLastItem(l, i) {
    return i >= l - 1;
  }
}

customElements.define(MrMetadata.is, MrMetadata);
