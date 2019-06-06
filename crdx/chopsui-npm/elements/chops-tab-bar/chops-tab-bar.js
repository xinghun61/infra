// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

export class ChopsTabBar extends LitElement {
  static get properties() {
    return {
      selected: String,
    };
  }

  static get styles() {
    return css`
      :host {
        align-items: center;
        border-bottom: 2px solid var(--chops-tab-bar-color, blue);
        color: var(--chops-tab-bar-color, blue);
        display: flex;
        margin-top: 8px;
      }
    `;
  }

  render() {
    return html`<slot></slot>`;
  }

  updated() {
    for (const item of this.querySelectorAll('chops-tab')) {
      item.checked = (item.getAttribute('name') === this.selected);
    }
  }
}

customElements.define('chops-tab-bar', ChopsTabBar);
