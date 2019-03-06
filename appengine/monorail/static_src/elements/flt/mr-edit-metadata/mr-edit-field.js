// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {dom} from '@polymer/polymer/lib/legacy/polymer.dom.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

import '../../chops/chops-button/chops-button.js';
import {fieldTypes} from '../../shared/field-types.js';
import {arrayDifference} from '../shared/flt-helpers.js';
import '../shared/flt-helpers.js';
import '../shared/mr-flt-styles.js';

/**
 * `<mr-edit-field>`
 *
 * A single edit input for a fieldDef + the values of the field.
 *
 */
export class MrEditField extends PolymerElement {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <style include="mr-flt-styles">
        :host {
          display: block;
        }
        :host([hidden]) {
          display: none;
        }
        input,
        select {
          @apply --mr-edit-field-styles;
        }
        input[type="checkbox"] {
          width: auto;
          height: auto;
        }
        .derived {
          font-style: italic;
          color: #222;
        }
        .multi-grid {
          width: 95%;
          display: grid;
          grid-gap: 4px;
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        }
        .multi-grid > input {
          width: unset;
        }
      </style>
      <template is="dom-if" if="[[_fieldIsEnum(type)]]">
        <template is="dom-if" if="[[multi]]">
          <template is="dom-repeat" items="[[options]]" as="option">
            <label title$="[[option.docstring]]">
              <input
                class="enum-input"
                type="checkbox"
                name$="[[name]]"
                value$="[[option.optionName]]"
                checked$="[[_optionInValues(initialValues, option.optionName)]]"
              />
              [[option.optionName]]
            </label>
          </template>
        </template>
        <select id="editSelect" hidden$="[[multi]]">
          <option value="">----</option>
          <template is="dom-repeat" items="[[options]]" as="option">
            <option
              value$="[[option.optionName]]"
              selected$="[[_computeIsSelected(_initialValue, option.optionName)]]"
            >
              [[option.optionName]]
              <template is="dom-if" if="[[option.docstring]]">
                - [[option.docstring]]
              </template>
            </option>
          </template>
        </select>
      </template>

      <template is="dom-if" if="[[_fieldIsBasic]]">
        <template is="dom-if" if="[[multi]]">
          <div id="multi-grid" class="multi-grid">
            <template is="dom-repeat" items="[[derivedValues]]">
              <div class="derived" title$="Derived: [[item]]">
                [[item]]
              </div>
            </template>
            <template is="dom-repeat" items="[[_multiInputs]]">
              <input
                id$="multi[[index]]"
                class="multi"
                type$="[[_inputType]]"
                aria-label$="[[name]] input #[[index]]"
                value$="[[item]]"
                data-ac-type$="[[_acType]]"
                autocomplete$="[[_computeDomAutocomplete(_acType)]]"
              />
            </template>
          </div>
          <chops-button on-click="_addEntry" class="de-emphasized">
            <i class="material-icons">add</i>
            Add entry
          </chops-button>
        </template>
        <input
          id="editInput"
          hidden$="[[multi]]"
          type$="[[_inputType]]"
          value$="[[_initialValue]]"
          data-ac-type$="[[_acType]]"
          autocomplete$="[[_computeDomAutocomplete(_acType)]]"
        />
      </template>
    `;
  }

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
      _inputType: {
        type: String,
        computed: '_computeInputType(type)',
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
    flush();
    this.setValue(this.initialValues);
  }

  setValue(v) {
    if (!Array.isArray(v)) {
      v = [v];
    }
    if (this.multi && this._fieldIsBasic) {
      dom(this.root).querySelectorAll('.multi').forEach((input, i) => {
        if (i < v.length) {
          input.value = v[i];
        } else {
          input.value = '';
        }
      });
    } else if (this.multi) {
      dom(this.root).querySelectorAll('.enum-input').forEach(
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
    return arrayDifference(
      this.getValues(), this.initialValues, this._equalsIgnoreCase);
  }

  getValuesRemoved() {
    if (!this.multi && this.getValues().length > 0) return [];
    return arrayDifference(
      this.initialValues, this.getValues(), this._equalsIgnoreCase);
  }

  getValues() {
    const valueList = [];
    if (!this.multi) {
      const val = this._getInput().value.trim();
      if (val) {
        valueList.push(val);
      }
    } else if (this._fieldIsEnum(this.type)) {
      dom(this.root).querySelectorAll('.enum-input').forEach((c) => {
        if (c.checked) {
          valueList.push(c.value.trim());
        }
      });
    } else {
      dom(this.root).querySelectorAll('.multi').forEach((input) => {
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
      return dom(this.root).querySelector('#editSelect');
    }
    return dom(this.root).querySelector('#editInput');
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

  _computeInputType(type) {
    if (type === fieldTypes.INT_TYPE) {
      return 'number';
    } else if (type === fieldTypes.DATE_TYPE) {
      return 'date';
    }
    return 'text';
  }

  _computeDomAutocomplete(acType) {
    if (acType) return 'off';
    return '';
  }

  _computeInitialValue(initialValues) {
    return (initialValues.length ? initialValues[0] : '');
  }

}

customElements.define(MrEditField.is, MrEditField);
