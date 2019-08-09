// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import deepEqual from 'deep-equal';
import {fieldTypes, EMPTY_FIELD_VALUE} from 'elements/shared/issue-fields.js';
import {arrayDifference, equalsIgnoreCase} from 'elements/shared/helpers.js';

import {SHARED_STYLES} from 'elements/shared/shared-styles';
import 'elements/chops/chops-chip-input/chops-chip-input.js';
import './mr-multi-input.js';
import './mr-multi-checkbox.js';

const MULTI_INPUTS_WITH_CHIPS_DISABLED = [
  fieldTypes.STR_TYPE, fieldTypes.DATE_TYPE, fieldTypes.URL_TYPE];

const BASIC_INPUT = 'BASIC_INPUT';
const MULTI_INPUT = 'MULTI_INPUT';
const CHIP_INPUT = 'CHIP_INPUT';
const CHECKBOX_INPUT = 'CHECKBOX_INPUT';
const SELECT_INPUT = 'SELECT_INPUT';

/**
 * `<mr-edit-field>`
 *
 * A single edit input for a fieldDef + the values of the field.
 *
 */
export class MrEditField extends LitElement {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          display: block;
        }
        :host([hidden]) {
          display: none;
        }
        mr-chip-input,
        mr-multi-input,
        chops-chip-input {
          width: var(--mr-edit-field-width);
        }
        input,
        select {
          width: var(--mr-edit-field-width);
          padding: var(--mr-edit-field-padding);
        }
      `,
    ];
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      ${this._renderInput()}
    `;
  }

  _renderInput() {
    switch (this._widgetType) {
      case CHECKBOX_INPUT:
        return html`
          <mr-multi-checkbox
            .options=${this.options}
            .values=${[...this.values]}
            @change=${this._changeHandler}
          ></mr-multi-checkbox>
        `;
      case SELECT_INPUT:
        return html`
          <select
            id="editSelect"
            aria-label=${this.name}
            @change=${this._changeHandler}
          >
            <option value="">${EMPTY_FIELD_VALUE}</option>
            ${this.options.map((option) => html`
              <option
                value=${option.optionName}
                .selected=${this.value === option.optionName}
              >
                ${option.optionName}
                ${option.docstring ? ' = ' + option.docstring : ''}
              </option>
            `)}
          </select>
        `;
      case CHIP_INPUT:
        return html`
          <chops-chip-input
            .immutableValues=${this.derivedValues}
            .initialValues=${[...this.initialValues]}
            .name=${this.name}
            .acType=${this.acType}
            .autocomplete=${this._domAutocomplete}
            .placeholder="Add ${this.name}"
            @change=${this._changeHandler}
          ></chops-chip-input>
        `;
      case MULTI_INPUT:
        return html`
          <mr-multi-input
            .immutableValues=${this.derivedValues}
            .initialValues=${[...this.initialValues]}
            .name=${this.name}
            .addEntryText="Add ${this.name}"
            .type=${this._html5InputType}
            @change=${this._changeHandler}
          ></mr-multi-input>
        `;
      case BASIC_INPUT:
        return html`
          <input
            id="editInput"
            type=${this._html5InputType}
            .value=${this.value}
            data-ac-type=${this.acType}
            autocomplete=${this._domAutocomplete}
            placeholder=${this.placeholder}
            @keyup=${this._changeHandler}
            @change=${this._changeHandler}
            @focus=${this._runLegacyAcFocus}
            aria-label=${this.name}
          />
        `;
      default:
        return '';
    }
  }

  static get properties() {
    return {
      // TODO(zhangtiff): Redesign this a bit so we don't need two separate
      // ways of specifying "type" for a field. Right now, "type" is mapped to
      // the Monorail custom field types whereas "acType" includes additional
      // data types such as components, and labels.
      // String specifying what kind of autocomplete to add to this field.
      acType: {type: String},
      // "type" is based on the various custom field types available in
      // Monorail.
      type: {type: String},
      multi: {type: Boolean},
      name: {type: String},
      // Only used for basic, non-repeated fields.
      placeholder: {type: String},
      initialValues: {
        type: Array,
        hasChanged(newVal, oldVal) {
          // Prevent extra recomputations of the same initial value causing
          // values to be reset.
          return !deepEqual(newVal, oldVal);
        },
      },
      // The ucrrent user-inputted values for a field.
      values: {type: Array},
      derivedValues: {type: Array},
      // For enum fields, the possible options that you have. Each entry is a
      // label type with an additional optionName field added.
      options: {type: Array},
      _checkboxRef: {type: Object},
      _selectRef: {type: Object},
      _multiInputRef: {type: Object},
      _inputRef: {type: Object},
    };
  }

  constructor() {
    super();
    this.initialValues = [];
    this.values = [];
    this.derivedValues = [];
    this.options = [];
    this.multi = false;

    this.actType = '';
    this.placeholder = '';
    this.type = '';
  }

  update(changedProperties) {
    if (changedProperties.has('initialValues')) {
      // Assume we always want to reset the user's input when initial
      // values change.
      this.reset();
    }
    super.update(changedProperties);
  }

  updated(changedProperties) {
    if (changedProperties.has('type') || changedProperties.has('multi')) {
      this._checkboxRef = this.shadowRoot.querySelector('mr-multi-checkbox');
      this._selectRef = this.shadowRoot.querySelector('#editSelect');
      this._multiInputRef = this.shadowRoot.querySelector('mr-multi-input');
      this._chipInputRef = this.shadowRoot.querySelector('chops-chip-input');
      this._inputRef = this.shadowRoot.querySelector('#editInput');
    }
  }

  get value() {
    return this._getSingleValue(this.values);
  }

  get _widgetType() {
    const type = this.type;
    const multi = this.multi;
    if (type === fieldTypes.ENUM_TYPE) {
      if (multi) {
        return CHECKBOX_INPUT;
      }
      return SELECT_INPUT;
    } else {
      if (multi) {
        if (!this.acType && MULTI_INPUTS_WITH_CHIPS_DISABLED.includes(type)) {
          return MULTI_INPUT;
        }
        return CHIP_INPUT;
      }
      return BASIC_INPUT;
    }
  }

  get _html5InputType() {
    const type = this.type;
    if (type === fieldTypes.INT_TYPE) {
      return 'number';
    } else if (type === fieldTypes.DATE_TYPE) {
      return 'date';
    }
    return 'text';
  }

  get _domAutocomplete() {
    const acType = this.acType;
    if (acType) return 'off';
    return '';
  }

  focus() {
    const input = this._getInput();
    if (input && input.focus) {
      input.focus();
    }
  }

  _getInput() {
    switch (this._widgetType) {
      case CHECKBOX_INPUT:
        return this._checkboxRef;
      case SELECT_INPUT:
        return this._selectRef;
      case MULTI_INPUT:
        return this._multiInputRef;
      case CHIP_INPUT:
        return this._chipInputRef;
      case BASIC_INPUT:
      default:
        return this._inputRef;
    }
  }

  reset() {
    this.setValue(this.initialValues);
  }

  setValue(v) {
    let values = v;
    if (!Array.isArray(v)) {
      values = !!v ? [v] : [];
    }
    this.values = [...values];
    const input = this._getInput();

    if (input && input.setValues) {
      input.setValues([...this.values]);
    }
  }

  getValuesAdded() {
    if (!this.values || !this.values.length) return [];
    return arrayDifference(
        this.values, this.initialValues, equalsIgnoreCase);
  }

  getValuesRemoved() {
    if (!this.multi && (!this.values || this.values.length > 0)) return [];
    return arrayDifference(
        this.initialValues, this.values, equalsIgnoreCase);
  }

  _changeHandler(e) {
    const input = e.target;
    if (input.getValues) {
      // Our custom input widgets all have a "getValues" function.
      this.values = input.getValues();
    } else {
      // Is a native input element.
      const value = input.value.trim();
      this.values = value.length ? [value] : [];
    }

    this.dispatchEvent(new Event('change'));
  }

  _getSingleValue(arr) {
    return (arr && arr.length) ? arr[0] : '';
  }

  // TODO(zhangtiff): Delete this code once deprecating legacy autocomplete.
  // See: http://crbug.com/monorail/5301
  _runLegacyAcFocus(e) {
    if (window._ac_onfocus) {
      _ac_onfocus(e);
    }
  }
}

customElements.define('mr-edit-field', MrEditField);
