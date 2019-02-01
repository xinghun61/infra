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
      // TODO(zhangtiff): Redesign this a bit so we don't need two separate
      // ways of specifying "type" for a field. Right now, "type" is mapped to
      // the Monorail custom field types whereas "acType" includes additional
      // data types such as components, and labels.
      // String specifying what kind of autocomplete to add to this field.
      acType: String,
      type: String,
      multi: {
        type: Boolean,
        value: false,
      },
      name: String,
      initialValues: {
        type: Array,
        value: () => [],
        observer: 'reset',
      },
      derivedValues: {
        type: Array,
        value: [],
      },
      // For enum fields, the possible options that you have. Each entry is a
      // label type with an additional optionName field added.
      options: {
        type: Array,
        value: () => [],
      },
      _acType: {
        type: String,
        computed: '_computeAcType(acType, type)',
      },
      // Set to true if a field uses a standard input instead of any sort of
      // fancier edit type.
      _fieldIsBasic: {
        type: Boolean,
        computed: '_computeFieldIsBasic(type)',
        value: true,
      },
      _multiInputs: {
        type: Array,
        value: [''],
      },
      _initialValue: {
        type: String,
        computed: '_computeInitialValue(initialValues)',
      },
      _multiGridClass: {
        type: String,
        value: 'multi-grid',
        computed: '_computeMultiGridClass(type)',
      },
    };
  }

  focus() {
    if (this._fieldIsBasic && !this.multi) {
      this._getInput().focus();
    }
  }

  reset() {
    this._multiInputs = this.initialValues.concat(['']);
    if (!this.isConnected) return;
    Polymer.flush();
    this.setValue(this.initialValues);
  }

  setValue(v) {
    if (!Array.isArray(v)) {
      v = [v];
    }
    if (this.multi && this._fieldIsBasic) {
      Polymer.dom(this.root).querySelectorAll('.multi').forEach((input, i) => {
        if (i < v.length) {
          input.value = v[i];
        } else {
          input.value = '';
        }
      });
    } else if (this.multi) {
      Polymer.dom(this.root).querySelectorAll('.enum-input').forEach(
        (checkbox) => {
          checkbox.checked = this._optionInValues(v, checkbox.value);
        }
      );
    } else if (this._fieldIsBasic) {
      this._getInput().value = v.length > 0 ? v[0] : '';
    } else {
      const input = this._getInput();
      const options = Array.from(input.querySelectorAll('option'));
      if (v.length == 0) {
        input.selectedIndex = null;
      } else {
        input.selectedIndex = options.findIndex((option) => {
          return this._computeIsSelected(v[0], option.value);
        });
      }
    }
  }

  getValuesAdded() {
    if (!this.getValues().length) return [];
    return fltHelpers.arrayDifference(this.getValues(), this.initialValues,
      this._equalsIgnoreCase);
  }

  getValuesRemoved() {
    if (!this.multi && this.getValues().length > 0) return [];
    return fltHelpers.arrayDifference(this.initialValues, this.getValues(),
      this._equalsIgnoreCase);
  }

  getValues() {
    const valueList = [];
    if (!this.multi) {
      const val = this._getInput().value.trim();
      if (val) {
        valueList.push(val);
      }
    } else if (this._fieldIsEnum(this.type)) {
      Polymer.dom(this.root).querySelectorAll('.enum-input').forEach((c) => {
        if (c.checked) {
          valueList.push(c.value.trim());
        }
      });
    } else {
      Polymer.dom(this.root).querySelectorAll('.multi').forEach((input) => {
        const val = input.value.trim();
        if (val.length) {
          valueList.push(val);
        }
      });
    }
    return valueList;
  }

  getValue() {
    return this._getInput().value.trim();
  }

  _addEntry() {
    this.push('_multiInputs', '');
  }

  _equalsIgnoreCase(a, b) {
    return a.toLowerCase() === b.toLowerCase();
  }

  // TODO(zhangtiff): We want to gradually make this list longer as we handle
  // all custom input cases.
  _computeFieldIsBasic(type) {
    return !(this._fieldIsEnum(type));
  }

  _fieldIsEnum(type) {
    return type === fieldTypes.ENUM_TYPE;
  }

  _fieldIsUser(type) {
    return type === fieldTypes.USER_TYPE;
  }

  _getInput() {
    if (this._fieldIsEnum(this.type) && !this.multi) {
      return Polymer.dom(this.root).querySelector('#editSelect');
    }
    return Polymer.dom(this.root).querySelector('#editInput');
  }

  _optionInValues(values, optionName) {
    return values.includes(optionName);
  }

  _computeIsSelected(initialValue, optionName) {
    return initialValue === optionName;
  }

  _computeAcType(acType, type) {
    if (this._fieldIsUser(type)) {
      return 'owner';
    }
    return acType;
  }

  _computeDomAutocomplete(acType) {
    if (acType) return 'off';
    return '';
  }

  _computeMultiGridClass(type) {
    if (this._fieldIsUser(type)) {
      return 'user-multi-grid';
    }
    return 'multi-grid';
  }

  _computeInitialValue(initialValues) {
    return (initialValues.length ? initialValues[0] : '');
  }

}

customElements.define(MrEditField.is, MrEditField);
