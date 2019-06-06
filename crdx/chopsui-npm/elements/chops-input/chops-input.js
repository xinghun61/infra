// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

export class ChopsInput extends LitElement {
  static get properties() {
    return {
      autofocus: {type: Boolean},
      disabled: {type: Boolean, reflect: true},
      focused: {type: Boolean, reflect: true},
      label: {type: String},
      value: {type: String},
    };
  }

  static get styles() {
    return css`
      :host {
        align-items: center;
        border-radius: 4px;
        border: 1px solid var(--chops-input-label-color, grey);
        cursor: text;
        display: flex;
        justify-content: space-between;
        padding: 4px;
        position: relative;
      }
      #label {
        background-color: var(--chops-input-background-color, white);
        color: var(--chops-input-label-color, grey);
        font-size: smaller;
        padding: 4px;
        position: absolute;
        transform: translate(0px, -1.5em);
        white-space: nowrap;
      }
      :host([disabled]) {
        border: 1px solid var(--chops-input-disabled-color, lightgrey);
        cursor: unset;
      }
      :host([focused]) {
        border: 2px solid var(--chops-input-focused-color, blue);
        padding: 3px;
      }
      :host([focused]) #label {
        color: var(--chops-input-focused-color, blue);
      }
      :host([error]) {
        border-color: var(--chops-input-error-color, red);
      }
      input {
        background-color: inherit;
        border: 0;
        box-sizing: border-box;
        flex-grow: 1;
        font-size: inherit;
        outline: none;
        padding: 8px 4px 4px 4px;
        width: 100%;
      }
    `;
  }

  constructor() {
    super();
    this.autofocus = false;
    this.disabled = false;
    this.focused = false;
    this.label = '';
    this.value = '';
  }

  render() {
    return html`
      <div id="label">${this.label}</div>
      <input
          size="0"
          ?disabled="${this.disabled}"
          .value="${this.value}"
          @blur="${this._onBlur}"
          @focus="${this._onFocus}"
          @keyup="${this._onKeyup}"></input>
      <slot></slot>
    `;
  }

  connectedCallback() {
    super.connectedCallback();
    if (this.autofocus) {
      this.focus();
    }
    this.addEventListener('click', () => this.focus());
  }

  firstUpdated() {
    this.native = this.shadowRoot.querySelector('input');
  }

  async _onFocus(event) {
    this.focused = true;
  }

  async _onBlur(event) {
    this.focused = false;
  }

  async focus() {
    await this.updateComplete;
    if (!this.native) return;
    this.native.focus();

    // Sometimes calling focus() doesn't dispatch the focus event.
    this.dispatchEvent(new CustomEvent('focus', {
      bubbles: true,
      composed: true,
    }));
  }

  async blur() {
    await this.updateComplete;
    if (!this.native) return;
    this.native.blur();
  }

  async _onKeyup(event) {
    this.value = event.target.value;
  }
}

customElements.define('chops-input', ChopsInput);
