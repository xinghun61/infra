// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

const DEFAULT_TIMEOUT = 10;

/**
 * `<chops-snackbar>`
 *
 * A container for showing messages in a snackbar.
 *
 */
export class ChopsSnackbar extends LitElement {
  static get styles() {
    return css`
      :host {
        align-items: center;
        background-color: #333;
        border-radius: 6px;
        bottom: 1em;
        color: hsla(0, 0%, 100%, .87);
        display: flex;
        font-size: var(--chops-large-font-size);
        left: 1em;
        padding: 16px;
        position: fixed;
      }
      :host([hidden]) {
        visibility: hidden;
      }
      button {
        background: none;
        border: none;
        color: inherit;
        cursor: pointer;
        margin: 0;
        margin-left: 8px;
        padding: 0;
      }
    `;
  }

  static get properties() {
    return {
      timeout: {
        type: Number,
      },
      hidden: {
        type: Boolean,
        reflect: true,
      },
    };
  }

  constructor() {
    super();
    this.timeout = DEFAULT_TIMEOUT;
  }

  updated(changedProperties) {
    if (changedProperties.has('hidden') && !this.hidden) {
      setTimeout(this.close.bind(this), this.timeout * 1000);
    }
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <slot></slot>
      <button @click=${this.close}>
        <i class="material-icons">close</i>
      </button>
    `;
  }

  close() {
    this.hidden = true;
  }
}

customElements.define('chops-snackbar', ChopsSnackbar);
