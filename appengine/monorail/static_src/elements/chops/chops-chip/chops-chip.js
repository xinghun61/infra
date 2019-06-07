// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

/**
 * `<chops-chip>` displays a single chip.
 *
 */
export class ChopsChip extends LitElement {
  static get properties() {
    return {
      icon: {type: String},
      focusable: {
        type: Boolean,
        reflect: true,
      },
      trailingIconLabel: {type: String},
    };
  }

  static get styles() {
    return css`
      :host {
        --chops-chip-bg-color: var(--chops-blue-gray-50);
        display: inline-flex;
        padding: 0.1em 8px;
        line-height: 140%;
        margin: 0 2px;
        border-radius: 16px;
        background: var(--chops-chip-bg-color);
        align-items: center;
        font-size: var(--chops-main-font-size);
        outline: none;
        box-sizing: border-box;
        border: 1px solid var(--chops-chip-bg-color);
      }
      :host(:focus) {
        background: var(--chops-primary-accent-bg);
        border: 1px solid var(--chops-light-accent-color);
      }
      :host([hidden]) {
        display: none;
      }
      button {
        border-radius: 50%;
        cursor: pointer;
        background: 0;
        border: 0;
        padding: 0;
        margin-right: -6px;
        margin-left: 4px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition: background-color 0.2s ease-in-out;
      }
      button[hidden] {
        display: none;
      }
      button:hover {
        background: var(--chops-gray-300);
      }
      i.material-icons {
        font-size: 14px;
        color: var(--chops-primary-icon-color);
        user-select: none;
      }
    `;
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <slot></slot>
      ${this.icon ? html`
        <button
          @click=${this.clickIcon}
          aria-label=${this.trailingIconLabel}
        ><i
          class="material-icons"
          aria-hidden="true"}
        >${this.icon}</i></button>
      `: ''}
    `;
  }

  update(changedProperties) {
    if (changedProperties.has('focusable')) {
      this.tabIndex = this.focusable ? '0' : undefined;
    }
    super.update(changedProperties);
  }

  clickIcon(e) {
    this.dispatchEvent(new CustomEvent('click-icon'));
  }
}
customElements.define('chops-chip', ChopsChip);
