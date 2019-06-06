// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

export class ChopsTab extends LitElement {
  static get properties() {
    return {
      checked: {
        type: Boolean,
        reflect: true,
      },
      name: {type: String},
    };
  }

  static get styles() {
    return css`
      :host {
        background-color: var(--chops-tab-background-color, lightblue);
        border-left: 1px solid var(--chops-tab-color, blue);
        border-right: 1px solid var(--chops-tab-color, blue);
        cursor: pointer;
        padding: 8px;
      }
      :host([checked]) {
        background-color: var(--chops-tab-color, blue);
        color: var(--chops-tab-checked-color, white);
        text-shadow: 1px 0 0 currentColor;
      }
    `;
  }

  render() {
    return html`<slot></slot>`;
  }
}

customElements.define('chops-tab', ChopsTab);
