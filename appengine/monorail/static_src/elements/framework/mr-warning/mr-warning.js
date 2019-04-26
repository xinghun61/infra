// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';


/**
 * `<mr-warnings>`
 *
 * A container for showing warnings.
 *
 */
export class MrWarning extends LitElement {
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
        border: 1px solid #FF6F00;
        border-radius: 4px;
        background: #FFF8E1;
      }
      :host([hidden]) {
        display: none;
      }
      i.material-icons {
        color: #FF6F00;
        margin-right: 4px;
      }
    `;
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <i class="material-icons">warning</i>
      <slot></slot>
    `;
  }
}

customElements.define('mr-warning', MrWarning);
