// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {PolymerElement, html} from '@polymer/polymer';

import '../../chops/chops-button/chops-button.js';
import '../../shared/mr-shared-styles.js';
import {fieldTypes} from '../../shared/field-types.js';
import {flush} from '@polymer/polymer/lib/utils/flush';


const DELIMITER_REGEX = /[,;\s+]/;

/**
 * `<mr-multi-input>`
 *
 * A multi input that creates one HTML input element per value. This
 * is especially useful for multivalued fields that make use of native
 * HTML5 input types such as dates or fields which cannot be delimited.
 *
 */
export class MrMultiInput extends PolymerElement {
  static get template() {
    return html`
      <style include="mr-shared-styles">
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
          @apply --mr-edit-field-styles;
          width: unset;
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
      </style>
      <template is="dom-repeat" items="[[immutableValues]]">
        <div class="derived" title$="Derived: [[item]]">
          [[item]]
        </div>
      </template>
      <template is="dom-repeat" items="[[_multiInputs]]">
        <input
          id$="multi[[index]]"
          type$="[[type]]"
          aria-label$="[[name]] input #[[index]]"
          value$="[[item]]"
          data-ac-type$="[[acType]]"
          autocomplete$="[[autocomplete]]"
          on-keyup="_onKeyup"
          on-blur="_onBlur"
        />
      </template>
      <chops-button on-click="_addEntry" class="de-emphasized">
        [[addEntryText]]
      </chops-button>
    `;
  }

  static get is() {
    return 'mr-multi-input';
  }

  static get properties() {
    return {
      name: String,
      initialValues: {
        type: Array,
        value: () => [],
        observer: 'reset',
      },
      immutableValues: Array,
      type: {
        type: String,
        value: 'text',
      },
      acType: String,
      autocomplete: String,
      addEntryText: {
        type: String,
        value: 'Add entry',
      },
      delimiterRegex: {
        type: Object,
        value: () => DELIMITER_REGEX,
      },
      _isDelimitable: {
        type: Boolean,
        computed: '_computeIsDelimitable(type)',
      },
      _multiInputs: {
        type: Array,
        value: () => [''],
      },
    };
  }

  reset() {
    this._setValuesForInputs(this.initialValues);
  }

  getValues() {
    const valueList = [];

    this.shadowRoot.querySelectorAll('input').forEach((input) => {
      const value = input.value.trim();
      if (value) {
        if (this._isDelimitable) {
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

  setValues(values) {
    this.initialValues = values;

    this.reset();
  }

  _addEntry() {
    this.push('_multiInputs', '');
  }

  _onKeyup() {
    this.dispatchEvent(new CustomEvent('change'));
  }

  _onBlur() {
    this._postProcess();
    this.dispatchEvent(new CustomEvent('blur'));
  }

  _computeIsDelimitable(type) {
    return ![fieldTypes.STR_TYPE, fieldTypes.URL_TYPE,
      fieldTypes.DATE_TYPE].includes(type);
  }

  _postProcess() {
    this._setValuesForInputs(this.getValues());
  }

  _setValuesForInputs(values) {
    if (values.length >= this._multiInputs.length) {
      // Add new input boxes if there aren't enough.
      this._multiInputs = values.concat(['']);
      flush();
    }

    this.shadowRoot.querySelectorAll('input').forEach((input, i) => {
      if (i < values.length) {
        input.value = values[i];
      } else {
        input.value = '';
      }
    });
  }
}

customElements.define(MrMultiInput.is, MrMultiInput);
