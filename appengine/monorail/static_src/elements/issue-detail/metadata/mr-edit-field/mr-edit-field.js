// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {fieldTypes} from 'elements/shared/field-types.js';
import {arrayDifference, equalsIgnoreCase} from 'elements/shared/helpers.js';

import 'elements/shared/mr-shared-styles.js';
import './mr-multi-input.js';
import './mr-multi-checkbox.js';

const BASIC_INPUT = 'BASIC_INPUT';
const MULTI_INPUT = 'MULTI_INPUT';
const CHECKBOX_INPUT = 'CHECKBOX_INPUT';
const SELECT_INPUT = 'SELECT_INPUT';

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
      <style include="mr-shared-styles">
        :host {
          display: block;
        }
        :host([hidden]) {
          display: none;
        }
        mr-multi-input {
          width: 95%;
        }
        input,
        select {
          @apply --mr-edit-field-styles;
        }
      </style>
      <mr-multi-checkbox
        hidden$="[[!_inputIsWidget(_widgetType, 'CHECKBOX_INPUT')]]"
        options="[[options]]"
        values="[[_cloneValues(initialValues)]]"
        on-change="_onChange"
      ></mr-multi-checkbox>

      <select
        hidden$="[[!_inputIsWidget(_widgetType, 'SELECT_INPUT')]]"
        id="editSelect"
        on-change="_onChange"
        aria-label$="[[name]]"
      >
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

      <mr-multi-input
        hidden$="[[!_inputIsWidget(_widgetType, 'MULTI_INPUT')]]"
        immutable-values="[[derivedValues]]"
        initial-values="[[_cloneValues(initialValues)]]"
        name="[[name]]"
        add-entry-text="Add [[name]]"
        type="[[_html5InputType]]"
        ac-type="[[acType]]"
        autocomplete="[[_domAutocomplete]]"
        on-change="_onChange"
        on-blur="_onChange"
      ></mr-multi-input>

      <input
        hidden$="[[!_inputIsWidget(_widgetType, 'BASIC_INPUT')]]"
        id="editInput"
        type$="[[_html5InputType]]"
        value$="[[_initialValue]]"
        data-ac-type$="[[acType]]"
        autocomplete$="[[_domAutocomplete]]"
        placeholder$="[[placeholder]]"
        on-keyup="_onChange"
        on-focus="_runLegacyAcFocus"
        aria-label$="[[name]]"
      />
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
      // "type" is based on the various custom field types available in
      // Monorail.
      type: String,
      multi: {
        type: Boolean,
        value: false,
      },
      name: String,
      // Only used for basic, non-repeated fields.
      placeholder: String,
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
      _domAutocomplete: {
        type: String,
        computed: '_computeDomAutocomplete(acType)',
      },
      _widgetType: {
        type: String,
        computed: '_computeWidgetType(type, multi)',
      },
      _html5InputType: {
        type: String,
        computed: '_computeHtml5InputType(type)',
      },
      _initialValue: {
        type: String,
        computed: '_computeInitialValue(initialValues)',
      },
    };
  }

  focus() {
    const input = this._getInput();
    if (input && input.focus) {
      input.focus();
    }
  }

  reset() {
    this.setValue(this.initialValues);
  }

  setValue(v) {
    const values = Array.isArray(v) ? v : [v];
    const input = this._getInput();

    if (input.setValues) {
      input.setValues(this._cloneValues(values));
    } else if (this._widgetType === BASIC_INPUT) {
      input.value = this._getSingleValue(values);
    } else if (this._widgetType === SELECT_INPUT) {
      const newValue = this._getSingleValue(values);

      if (newValue) {
        const options = [...input.querySelectorAll('option')];
        input.value = newValue;
        input.selectedIndex = options.findIndex(
          (option) => this._computeIsSelected(newValue, option.value));
      } else {
        input.selectedIndex = null;
      }
    }
  }

  getValuesAdded() {
    if (!this.getValues().length) return [];
    return arrayDifference(
      this.getValues(), this.initialValues, equalsIgnoreCase);
  }

  getValuesRemoved() {
    if (!this.multi && this.getValues().length > 0) return [];
    return arrayDifference(
      this.initialValues, this.getValues(), equalsIgnoreCase);
  }

  getValues() {
    const input = this._getInput();
    if (input.getValues) {
      // Out custom input widgets all have a "getValues" function.
      return input.getValues();
    }
    // Is a native input element.
    const value = input.value.trim();
    return value.length ? [value] : [];
  }

  getValue() {
    return this._getSingleValue(this.getValues());
  }

  _computeWidgetType(type, multi) {
    if (type === fieldTypes.ENUM_TYPE) {
      if (multi) {
        return CHECKBOX_INPUT;
      }
      return SELECT_INPUT;
    } else {
      if (multi) {
        return MULTI_INPUT;
      }
      return BASIC_INPUT;
    }
  }

  _inputIsWidget(widgetType, comparisonType) {
    return widgetType === comparisonType;
  }

  _getInput() {
    switch (this._widgetType) {
      case CHECKBOX_INPUT:
        return this.shadowRoot.querySelector('mr-multi-checkbox');
      case SELECT_INPUT:
        return this.shadowRoot.querySelector('#editSelect');
      case MULTI_INPUT:
        return this.shadowRoot.querySelector('mr-multi-input');
      case BASIC_INPUT:
      default:
        return this.shadowRoot.querySelector('#editInput');
    }
  }

  _computeIsSelected(initialValue, optionName) {
    return initialValue === optionName;
  }

  _computeHtml5InputType(type) {
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
    return this._getSingleValue(initialValues);
  }

  _onChange() {
    this.dispatchEvent(new CustomEvent('change'));
  }

  _cloneValues(arr) {
    return [...arr];
  }

  _getSingleValue(arr) {
    return arr.length ? arr[0] : '';
  }

  // TODO(zhangtiff): Delete this code once deprecating legacy autocomplete.
  // See: http://crbug.com/monorail/5301
  _runLegacyAcFocus(e) {
    if (window._ac_onfocus) {
      _ac_onfocus(e);
    }
  }
}

customElements.define(MrEditField.is, MrEditField);
