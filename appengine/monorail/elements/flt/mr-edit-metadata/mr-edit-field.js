'use strict';

/**
 * `<mr-edit-field>`
 *
 * A single edit input for a fieldDef + the values of the field.
 *
 */
class MrEditField extends Polymer.Element {
  static get is() {
    return 'mr-edit-field';
  }

  static get properties() {
    return {
      delimiter: {
        type: String,
        value: ',',
      },
      type: String,
      multi: {
        type: Boolean,
        value: false,
      },
      name: String,
      // Values is a one way mapping. Do not add expect values to represent the
      // current data in the form element. Use getValue() instead.
      values: {
        type: Array,
        value: () => [],
        notify: false,
      },
      value: String,
      // For enum fields, the possible options that you have. Each entry is a
      // label type.
      options: {
        type: Array,
        value: () => [],
      },
      _defaultValue: {
        type: String,
        computed: '_computeDefaultValue(value, values, multi)',
      },
      // Set to true if a field uses a standard input instead of any sort of
      // fancier edit type.
      _fieldIsBasic: {
        type: Boolean,
        computed: '_computeFieldIsBasic(type)',
        value: true,
      },
    };
  }

  focus() {
    if (this._fieldIsBasic) {
      this._getInput().focus();
    }
  }

  reset() {
    if (this._fieldIsBasic) {
      this._getInput().value = this._defaultValue;
    }
  }

  getValue() {
    if (this._fieldIsEnum(this.type)) {
      throw new Error('Enum values not implemented yet!');
    }
    const val = this._getInput().value;
    if (this.multi) {
      let valueList = val.split(this.delimiter);
      valueList = valueList.map((s) => (s.trim()));
      valueList = valueList.filter((s) => (s.length > 0));
      return valueList;
    }
    return val;
  }

  // TODO(zhangtiff): We want to gradually make this list longer as we handle
  // all custom input cases.
  _computeFieldIsBasic(type) {
    return !(this._fieldIsEnum(type));
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

  _computeDefaultValue(value, values, multi) {
    if (multi) {
      return values.join(',');
    }
    return value;
  }

  _getInput() {
    return Polymer.dom(this.root).querySelector('#editInput');
  }

  _opionInValues(values, option) {
    return values.includes(option);
  }

  _stripPrefix(s, prefix) {
    // Add 1 for the dash (-) separator.
    return s.substring(prefix.length + 1);
  }

  _computeIsSelected(value, option) {
    return value === option;
  }
}

customElements.define(MrEditField.is, MrEditField);
