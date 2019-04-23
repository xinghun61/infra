// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

/**
 * `<chops-collapse>` displays a collapsible element.
 *
 */
export class ChopsCollapse extends LitElement {
  static get properties() {
    return {
      opened: {
        type: Boolean,
        reflect: true,
      },
      ariaHidden: {
        attribute: 'aria-hidden',
        type: Boolean,
        reflect: true,
      },
    };
  }

  static get styles() {
    return css`
      :host, :host([hidden]) {
        display: none;
      }
      :host([opened]) {
        display: block;
      }
    `;
  }

  render() {
    return html`
      <slot></slot>
    `;
  }

  static get is() {
    return 'chops-collapse';
  }

  constructor() {
    super();

    this.opened = false;
    this.ariaHidden = true;
  }

  update(changedProperties) {
    if (changedProperties.has('opened')) {
      this.ariaHidden = !this.opened;
    }
    super.update(changedProperties);
  }
}
customElements.define(ChopsCollapse.is, ChopsCollapse);
