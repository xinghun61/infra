// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import 'elements/chops/chops-button/chops-button.js';

export class MrChoiceButtons extends LitElement {
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
        grid-gap: 6px;
      }
      chops-button {
        font-size: var(--chops-large-font-size);
        padding: 4px 10px;
        background: var(--chops-choice-bg);
        text-decoration: none;
      }
      chops-button[selected] {
        background: var(--chops-blue-50);
      }
    `;
  };

  _setValue(e) {
    const oldValue = this.value;
    this.value = e.target.getAttribute('value');
    if (oldValue != this.value) {
      this.dispatchEvent(new CustomEvent('change'));
    }
  }
};

customElements.define('mr-choice-buttons', MrChoiceButtons);
