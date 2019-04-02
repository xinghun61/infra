// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {PolymerElement, html} from '@polymer/polymer';

/**
 * `<mr-multi-checkbox>`
 *
 * A web component for managing values in a set of checkboxes.
 *
 */
export class MrMultiCheckbox extends PolymerElement {
  static get template() {
    return html`
      <style>
        input[type="checkbox"] {
          width: auto;
          height: auto;
        }
      </style>
      <template is="dom-repeat" items="[[options]]" as="option">
        <label title$="[[option.docstring]]">
          <input
            type="checkbox"
            name$="[[name]]"
            value$="[[option.optionName]]"
            checked$="[[_optionInValues(values, option.optionName)]]"
            on-change="_onChange"
          />
          [[option.optionName]]
        </label>
      </template>
    `;
  }

  static get is() {
    return 'mr-multi-checkbox';
  }

  static get properties() {
    return {
      values: Array,
      options: Array,
    };
  }

  getValues() {
    const valueList = [];
    this.shadowRoot.querySelectorAll('input').forEach((c) => {
      if (c.checked) {
        valueList.push(c.value.trim());
      }
    });
    return valueList;
  }

  setValues(values) {
    this.shadowRoot.querySelectorAll('input').forEach(
      (checkbox) => {
        checkbox.checked = this._optionInValues(values, checkbox.value);
      }
    );
  }

  _optionInValues(values, optionName) {
    return values.includes(optionName);
  }

  _onChange() {
    this.dispatchEvent(new CustomEvent('change'));
  }
}

customElements.define(MrMultiCheckbox.is, MrMultiCheckbox);
