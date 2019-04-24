// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

/**
 * `<mr-warnings>`
 *
 * A container for showing warnings.
 *
 */
export class MrWarning extends PolymerElement {
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
      </style>
      <i class="material-icons">warning</i>
      <slot></slot>
    `;
  }

  static get is() {
    return 'mr-warning';
  }
}

customElements.define(MrWarning.is, MrWarning);
