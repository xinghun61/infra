// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import 'elements/chops/chops-button/chops-button.js';

// Three button selection menu.
export class MrButtonGroup extends LitElement {
  render() {
    return html`
      ${(this.options).map((option) => html`
        <chops-button class="button">${option}</chops-button>
      `)}
    `;
  }

  static get properties() {
    return {
      options: {type: Array},
    };
  };

  constructor() {
    super();
    this.options = [];
  };

  static get styles() {
    return css`
      .button {
        font-size: var(--chops-large-font-size);
        padding: 4px 10px;
        margin-left: 6px;
        background: var(--chops-choice-bg);
        text-decoration: none;
      }
    `;
  };
};

customElements.define('mr-button-group', MrButtonGroup);
