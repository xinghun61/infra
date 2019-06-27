// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

export class MrGridDropdown extends LitElement {
  render() {
    return html`
      ${this.text}:
      <select class="drop-down">
        ${(this.items).map((item) => html`
          <option>${item}</option>
        `)}
      </select>
      `;
  }

  static get properties() {
    return {
      text: {type: String},
      items: {type: Array},
    };
  };

  constructor() {
    super();
    this.items = [];
  };

  static get styles() {
    // define css file.
    return css`
      :host {
        font-size: var(--chops-large-font-size);
      }
      .drop-down {
        font-size: var(--chops-large-font-size);
      }
    `;
  };
};

customElements.define('mr-grid-dropdown', MrGridDropdown);

