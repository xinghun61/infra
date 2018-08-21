'use strict';

/**
 * `<mr-field-values>`
 *
 * Takes in a list of field values and a single fieldDef and displays them
 * according to their type.
 *
 */
class MrFieldValues extends Polymer.Element {
  static get is() {
    return 'mr-field-values';
  }

  static get properties() {
    return {
      name: String,
      type: Object,
      projectName: String,
      values: Array,
    };
  }

  _fieldIsDate(type) {
    return type === fieldTypes.DATE_TYPE;
  }

  _fieldIsEnum(type) {
    return type === fieldTypes.ENUM_TYPE;
  }

  _fieldIsInt(type) {
    return type === fieldTypes.INT_TYPE;
  }

  _fieldIsStr(type) {
    return type === fieldTypes.STR_TYPE;
  }

  _fieldIsUser(type) {
    return type === fieldTypes.USER_TYPE;
  }

  _fieldIsUrl(type) {
    return type === fieldTypes.URL_TYPE;
  }

  _fieldIsRemainingTypes(type) {
    return this._fieldIsDate(type) || this._fieldIsEnum(type) ||
      this._fieldIsInt(type) || this._fieldIsStr(type);
  }

  _isLastItem(l, i) {
    return i >= l - 1;
  }
}

customElements.define(MrFieldValues.is, MrFieldValues);
