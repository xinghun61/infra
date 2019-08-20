// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import 'elements/chops/chops-button/chops-button.js';

export class ChopsChoiceButtons extends LitElement {
  render() {
    return html`
      ${(this.options).map((option) => html`
        <chops-button
          ?selected=${this.value === option.value}
          @click=${this._setValue}
          value=${option.value}
        >${option.text}</chops-button>
      `)}
    `;
  }

  static get properties() {
    return {
      /**
       * Array of options where each option is an Object with keys:
       * {value, text}
       */
      options: {type: Array},
      value: {type: String},
    };
  };

  constructor() {
    super();
    this.options = [];
  };

  static get styles() {
    return css`
      :host {
        display: grid;
        grid-auto-flow: column;
        grid-template-columns: auto;
      }
      chops-button {
        color: var(--chops-gray-700);
        font-size: var(--chops-normal-font-size);
        padding: 4px 10px;
        background: var(--chops-choice-bg);
        text-decoration: none;
        border-radius: 16px;
        outline: none;
      }
      chops-button[selected] {
        background: var(--chops-blue-50);
        color: var(--chops-blue-900);
        border-radius: 16px;
      }
    `;
  };

  setValue(newValue) {
    if (newValue !== this.value) {
      this.value = newValue;
      this.dispatchEvent(new CustomEvent('change'));
    }
  }

  _setValue(e) {
    this.setValue(e.target.getAttribute('value'));
  }
};

customElements.define('chops-choice-buttons', ChopsChoiceButtons);
