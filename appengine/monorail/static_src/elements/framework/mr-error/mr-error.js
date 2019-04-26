// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';


/**
 * `<mr-error>`
 *
 * A container for showing errors.
 *
 */
export class MrError extends LitElement {
  static get styles() {
    return css`
      :host {
        display: flex;
        align-items: center;
        flex-direction: row;
        justify-content: flex-start;
        box-sizing: border-box;
        width: 100%;
        margin: 0.5em 0;
        padding: 0.25em 8px;
        border: 1px solid #B71C1C;
        border-radius: 4px;
        background: #FFEBEE;
      }
      :host([hidden]) {
        display: none;
      }
      i.material-icons {
        color: #B71C1C;
        margin-right: 4px;
      }
    `;
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <i class="material-icons">close</i>
      <slot></slot>
    `;
  }
}

customElements.define('mr-error', MrError);
