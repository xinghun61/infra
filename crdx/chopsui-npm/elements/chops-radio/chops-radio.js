// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

export class ChopsRadio extends LitElement {
  static get properties() {
    return {
      name: {type: String},
      checked: {type: Boolean},
      disabled: {type: Boolean},
    };
  }

  static get styles() {
    return css`
      input {
        display: none;
      }
      input:checked + label:before {
        border-color: var(--chops-radio-color, blue);
      }
      input:checked + label:after {
        transform: scale(1);
      }
      label {
        align-items: center;
        display: inline-flex;
        height: 20px;
        position: relative;
        padding: 0 30px;
        margin-bottom: 0;
        cursor: pointer;
        vertical-align: bottom;
        white-space: nowrap;
      }
      label:before, label:after {
        position: absolute;
        content: '';
        border-radius: 50%;
      }
      label:before {
        box-sizing: border-box;
        left: 0;
        top: 0;
        width: 20px;
        height: 20px;
        border: 2px solid rgba(0, 0, 0, 0.54);
      }
      label:after {
        top: 5px;
        left: 5px;
        width: 10px;
        height: 10px;
        transform: scale(0);
        background: var(--chops-radio-color, blue);
      }
      input:disabled + label:before,
      input:disabled + label:after {
        border-color: var(--chops-radio-disabled-color, darkgrey);
      }
      input:disabled:checked + label:before,
      input:disabled:checked + label:after {
        background: var(--chops-radio-disabled-color, darkgrey);
      }
    `;
  }

  constructor() {
    super();
    this.checked = false;
    this.disabled = false;
    this.name = '';
  }

  render() {
    return html`
      <input
          type="radio"
          id="native"
          .checked="${this.checked}"
          ?disabled="${this.disabled}"
          @change="${this._onChange}">
      <label for="native"><slot></slot></label>
    `;
  }

  _onChange(event) {
    this.dispatchEvent(new CustomEvent('change', {
      bubbles: true,
      composed: true,
      detail: {value: this.name},
    }));
  }
}

customElements.define('chops-radio', ChopsRadio);
