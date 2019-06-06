// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

export class ChopsCheckbox extends LitElement {
  static get properties() {
    return {
      checked: {type: Boolean},
      disabled: {type: Boolean},
    };
  }

  static get styles() {
    return css`
      :host {
        align-items: center;
        display: inline-flex;
        outline: none;
        width: 100%;
      }
      :host([hidden]) {
        visibility: hidden;
      }
      label {
        align-items: center;
        cursor: pointer;
        display: inline-flex;
        height: 32px;
        position: relative;
        width: 100%;
      }
      label:before, label:after {
        content: "";
        position: absolute;
        left: -22px;
        top: 8px;
      }
      label:before {
        background: var(--chops-checkbox-background-color, white);
        border-radius: 2px;
        border: 2px solid var(--chops-checkbox-border-color, black);
        cursor: pointer;
        height: 18px;
        width: 18px;
      }
      input {
        outline: 0;
        visibility: hidden;
      }
      input:checked + label:before {
        background: var(--chops-checkbox-checked-color, blue);
        border: 2px solid var(--chops-checkbox-checked-color, blue);
      }
      input:checked + label:after {
        border-color: var(--chops-checkbox-background-color, white);
        border-style: none none solid solid;
        border-width: 2px;
        height: 6px;
        left: -18px;
        top: 13px;
        transform: rotate(-45deg);
        width: 12px;
      }
      input:disabled + label:before {
        border-color: var(--chops-checkbox-disabled-color, darkgrey);
      }
      input:disabled:checked + label:before {
        background: var(--chops-checkbox-disabled-color, darkgrey);
      }
      *, *:before, *:after {
        box-sizing: border-box;
      }
    `;
  }

  constructor() {
    super();
    this.checked = false;
    this.disabled = false;
  }

  render() {
    return html`
      <input
          type="checkbox"
          id="native"
          .checked="${this.checked}"
          ?disabled="${this.disabled}"
          @change="${this._onChange}">
      <label for="native"><slot></slot></label>
    `;
  }

  firstUpdated() {
    this.native = this.shadowRoot.querySelector('input');
  }

  click() {
    this.native.click();
  }

  _onChange(event) {
    this.checked = !this.checked;
    this.dispatchEvent(new CustomEvent('change', {
      bubbles: true,
      composed: true,
      detail: {event},
    }));
  }
}

// Tests may load this module from multiple paths. If this module is already
// defined, don't try to redefine it.
if (!customElements.get('chops-checkbox')) {
  customElements.define('chops-checkbox', ChopsCheckbox);
}
