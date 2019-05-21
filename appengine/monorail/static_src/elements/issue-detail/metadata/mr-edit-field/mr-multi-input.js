// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import deepEqual from 'deep-equal';

import 'elements/chops/chops-button/chops-button.js';
import {fieldTypes} from 'elements/shared/field-types.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles';

const DELIMITER_REGEX = /[,;\s]/;
const DELIMITABLE_TYPES = [fieldTypes.STR_TYPE, fieldTypes.URL_TYPE,
  fieldTypes.DATE_TYPE];

/**
 * `<mr-multi-input>`
 *
 * A multi input that creates one HTML input element per value. This
 * is especially useful for multivalued fields that make use of native
 * HTML5 input types such as dates or fields which cannot be delimited.
 *
 */
export class MrMultiInput extends LitElement {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          display: grid;
          grid-gap: var(--mr-input-grid-gap);
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        }
        :host([hidden]) {
          display: none;
        }
        .derived {
          font-style: italic;
          color: var(--chops-text-color);
        }
        input {
          box-sizing: border-box;
          padding: var(--mr-edit-field-padding);
          font-size: var(--chops-main-font-size);
        }
        chops-button {
          /* Use grid to determine sizing for button, not
          * chops-button styles. */
          margin-left: unset;
          font-size: var(--chops-main-font-size);
          padding: 0 8px;
          text-align: left;
          justify-content: flex-start;
        }
      `,
    ];
  }

  render() {
    return html`
      ${this.immutableValues.map((value) => html`
        <div class="derived" title="Derived: ${value}">
          ${value}
        </div>
      `)}
      </template>
      ${this._multiInputs.map((value, i) => html`
        <input
          part="edit-field"
          id="multi${i}"
          type=${this.type}
          aria-label="${this.name} input #${i}"
          value=${value}
          data-ac-type=${this.acType}
          autocomplete=${this.autocomplete}
          @keyup=${this._onKeyup}
          @blur=${this._onBlur}
          @focus=${this._runLegacyAcFocus}
        />
      `)}
      <chops-button @click=${this._addEntry} class="de-emphasized">
        ${this.addEntryText}
      </chops-button>
    `;
  }

  static get properties() {
    return {
      name: {type: String},
      initialValues: {
        type: Array,
        hasChanged(newVal, oldVal) {
          // Prevent extra recomputations of the same initial value cause
          // values to be reset.
          return !deepEqual(newVal, oldVal);
        },
      },
      immutableValues: {type: Array},
      type: {type: String},
      acType: {type: String},
      autocomplete: {type: String},
      addEntryText: {type: String},
      delimiterRegex: {type: Object},
      _multiInputs: {type: Array},
    };
  }

  constructor() {
    super();
    this.immutableValues = [];
    this.initialValues = [];
    this.delimiterRegex = DELIMITER_REGEX;
    this._multiInputs = [''];
    this.type = 'text';
    this.addEntryText = 'Add entry';
  }

  updated(changedProperties) {
    if (changedProperties.has('initialValues')) {
      this.reset();
    }
  }

  async reset() {
    await this._setValuesForInputs(this.initialValues, true);
  }

  getValues() {
    const valueList = [];

    this.shadowRoot.querySelectorAll('input').forEach((input) => {
      const value = input.value.trim();
      if (value) {
        if (!DELIMITABLE_TYPES.includes(this.type)) {
          // Only split up values by comma for fields that use autocomplete.
          valueList.push(
            ...value.split(this.delimiterRegex).filter(Boolean));
        } else {
          valueList.push(value);
        }
      }
    });
    return valueList;
  }

  async setValues(values) {
    this.initialValues = values;

    await this.reset();
  }

  _addEntry() {
    this._multiInputs = this._multiInputs.concat(['']);
  }

  _onKeyup() {
    this.dispatchEvent(new CustomEvent('change'));
  }

  async _onBlur() {
    await this._setValuesForInputs(this.getValues());
    this.dispatchEvent(new CustomEvent('blur'));
  }

  async _setValuesForInputs(values, hardReset) {
    await this.updateComplete;
    // Note: Not all values may be applied to inputs here, but that's okay
    // because extra values will be created as new inputs.
    this.shadowRoot.querySelectorAll('input').forEach((input, i) => {
      if (i < values.length) {
        input.value = values[i];
      } else {
        input.value = '';
      }
    });

    // hardReset is used to optionally delete excess empty inputs.
    if (hardReset || values.length >= this._multiInputs.length) {
      // Add new input boxes if there aren't enough.
      this._multiInputs = values.concat(['']);
    }
  }

  // TODO(zhangtiff): Delete this code once deprecating legacy autocomplete.
  // See: http://crbug.com/monorail/5301
  _runLegacyAcFocus(e) {
    if (window._ac_onfocus) {
      _ac_onfocus(e);
    }
  }
}

customElements.define('mr-multi-input', MrMultiInput);
