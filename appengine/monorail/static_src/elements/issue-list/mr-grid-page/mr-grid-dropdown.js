// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {equalsIgnoreCase} from 'elements/shared/helpers.js';

export class MrGridDropdown extends LitElement {
  render() {
    return html`
      ${this.text}:
      <select
        class="drop-down"
        @change=${this._optionChanged}
      >
        ${(this.items).map((item) => html`
          <option .selected=${equalsIgnoreCase(item, this.selection)}>
            ${item}
          </option>
        `)}
      </select>
      `;
  }

  static get properties() {
    return {
      text: {type: String},
      items: {type: Array},
      selection: {type: String},
    };
  };

  constructor() {
    super();
    this.items = [];
    this.selection = 'None';
  };

  static get styles() {
    return css`
      :host {
        font-size: var(--chops-large-font-size);
      }
      .drop-down {
        font-size: var(--chops-large-font-size);
      }
    `;
  };

  _optionChanged(e) {
    this.selection = e.target.value;
    this.dispatchEvent(new CustomEvent('change'));
  };
};

customElements.define('mr-grid-dropdown', MrGridDropdown);

