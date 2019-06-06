// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

export class ChopsButton extends LitElement {
  static get styles() {
    return css`
      :host {
        align-items: center;
        background-color: var(--chops-button-background-color, lightblue);
        background-position: center;
        border-radius: 24px;
        border: 0px none hsl(231, 50%, 50%);
        box-shadow: var(--chops-button-shadow);
        color: var(--chops-button-color, blue);
        cursor: pointer;
        display: flex;
        height: var(--chops-button-height, 24px);
        justify-content: center;
        margin: 4px 8px;
        padding: 4px 8px;
        text-transform: uppercase;
        user-select: none;
      }
      * {
        flex-grow: 1
      }
      :host([disabled]) {
        background-color: var(--chops-button-disabled-background-color,
          lightgrey);
        box-shadow: none;
        color: var(--chops-button-disabled-color, grey);
        cursor: auto;
        pointer-events: none;
      }
      :host(:hover) {
        background: var(--chops-button-background-color, lightgrey)
          radial-gradient(circle, transparent 1%,
          var(--chops-button-background-color, lightgrey) 1%) center/15000%;
      }
      :host(:active) {
        background-color: var(--chops-button-active-color, dodgerblue);
        background-size: 100%;
      }
    `;
  }

  render() {
    return html`<slot></slot>`;
  }
}
customElements.define('chops-button', ChopsButton);
