/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

import '../../node_modules/@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

/**
 * `<mr-error>`
 *
 * A container for showing errors.
 *
 */
export class MrError extends PolymerElement {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style>
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
        }
      </style>
      <i class="material-icons">close</i>
      <slot></slot>
    `;
  }

  static get is() {
    return 'mr-error';
  }
}

customElements.define(MrError.is, MrError);
