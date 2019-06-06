// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

export class ChopsRadioGroup extends LitElement {
  static get properties() {
    return {
      selected: String,
    };
  }

  static get styles() {
    return css`
      :host {
        display: flex;
        flex-direction: column;
      }
      ::slotted(chops-radio) {
        margin: 4px 0;
      }
    `;
  }

  constructor() {
    super();
    this.selected = '';
    this.addEventListener('change', (event) => {
      this.selected = event.detail.value;
    });
  }

  render() {
    return html`<slot></slot>`;
  }

  updated(changedProperties) {
    if (!changedProperties.has('selected')) return;
    for (const item of this.querySelectorAll('chops-radio')) {
      item.checked = (item.getAttribute('name') === this.selected);
    }
    this.dispatchEvent(new CustomEvent('change', {
      bubbles: true,
      composed: true,
      detail: {value: this.selected},
    }));
  }
}

customElements.define('chops-radio-group', ChopsRadioGroup);
