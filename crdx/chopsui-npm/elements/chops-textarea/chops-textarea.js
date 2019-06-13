// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

export class ChopsTextarea extends LitElement {
  static get properties() {
    return {
      autofocus: {type: Boolean},
      focused: {
        type: Boolean,
        reflect: true,
      },
      label: {type: String},
      value: {type: String},
    };
  }

  static get styles() {
    return css`
      :host {
        border-radius: 4px;
        border: 1px solid var(--chops-textarea-label-color, grey);
        cursor: text;
        display: flex;
        margin-top: 1em;
        outline: none;
        padding: 4px;
        position: relative;
      }
      #label {
        background-color: var(--chops-textarea-background-color, white);
        color: var(--chops-textarea-label-color, grey);
        font-size: smaller;
        padding: 4px;
        position: absolute;
        transform: translate(0px, -1.5em);
        white-space: nowrap;
      }
      :host([focused]) {
        border: 2px solid var(--chops-textarea-focused-color, blue);
        padding: 3px;
      }
      :host([focused]) #label {
        color: var(--chops-textarea-focused-color, blue);
      }
      :host([error]) {
        border-color: var(--chops-textarea-error-color, red);
      }
      textarea {
        border: 0;
        flex-grow: 1;
        font-family: inherit;
        font-size: inherit;
        outline: none;
        padding: 4px;
      }
    `;
  }

  constructor() {
    super();
    this.autofocus = false;
    this.focused = false;
    this.label = '';
    this.value = '';
  }

  render() {
    return html`
      <div id="label">${this.label}</div>
      <textarea
          .value="${this.value}"
          @blur="${this._onBlur}"
          @focus="${this._onFocus}"
          @keyup="${this._onKeyup}"></textarea>
    `;
  }

  async connectedCallback() {
    super.connectedCallback();
    if (this.autofocus) {
      this.focus();
    }
    this.addEventListener('click', () => this.focus());
  }

  firstUpdated() {
    this.native = this.shadowRoot.querySelector('textarea');
  }

  async focus() {
    await this.updateComplete;
    if (!this.native) return;
    this.native.focus();
  }

  async blur() {
    await this.updateComplete;
    if (!this.native) return;
    this.native.blur();
  }

  async _onFocus(event) {
    this.focused = true;
  }

  async _onBlur(event) {
    this.focused = false;
  }

  async _onKeyup(event) {
    this.value = event.target.value;
  }
}

customElements.define('chops-textarea', ChopsTextarea);
