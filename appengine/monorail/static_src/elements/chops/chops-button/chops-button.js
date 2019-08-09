// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

const DEFAULT_INPUT_KEYS = [13, 32];


/**
 * `<chops-button>` displays a styled button component with a few niceties.
 *
 * @customElement
 * @demo /demo/chops-button_demo.html
 */
export class ChopsButton extends LitElement {
  static get styles() {
    return css`
      :host {
        background: hsla(0, 0%, 95%, 1);
        margin: 0.25em 4px;
        padding: 0.5em 16px;
        cursor: pointer;
        border-radius: 3px;
        text-align: center;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        user-select: none;
        transition: filter 0.3s ease-in-out, box-shadow 0.3s ease-in-out;
        font-family: Roboto, Noto, sans-serif;
      }
      :host([hidden]) {
        display: none;
      }
      :host([raised]) {
        box-shadow: 0px 2px 8px -1px hsla(0, 0%, 0%, 0.5);
      }
      :host(:hover) {
        filter: brightness(95%);
      }
      :host(:active) {
        filter: brightness(115%);
      }
      :host([raised]:active) {
        box-shadow: 0px 1px 8px -1px hsla(0, 0%, 0%, 0.5);
      }
      :host([disabled]),
      :host([disabled]:hover) {
        filter: grayscale(30%);
        opacity: 0.4;
        background: hsla(0, 0%, 87%, 1);
        cursor: default;
        pointer-events: none;
        box-shadow: none;
      }
    `;
  }
  render() {
    return html`
      <slot></slot>
    `;
  }

  static get properties() {
    return {
      /** Whether the button is available for input or not. */
      disabled: {
        type: Boolean,
        reflect: true,
      },
      /**
       * For accessibility. These are the keys that you can use to fire the
       * onclick event for chops-button. The value is an Array of
       * JavaScript key input codes, defaulting to space and enter keys.
       */
      inputKeys: {
        type: Array,
      },
      /**
       * If true, the element currently has focus. Changed through focus
       * and blur event listeners.
       */
      focused: {
        type: Boolean,
        reflect: true,
      },
      /** Whether the button should have a shadow or not. */
      raised: {
        type: Boolean,
        value: false,
        reflect: true,
      },
      /** Used for accessibility to state that this component is a button. **/
      role: {
        type: String,
        value: 'button',
        reflect: true,
      },
      /** Causes the button to be focusable for accessbility. **/
      tabindex: {
        type: Number,
        reflect: true,
      },
      _boundKeypressHandler: {
        type: Object,
      },
      _boundFocusBlurHandler: {
        type: Object,
      },
    };
  }

  constructor() {
    super();

    this.focused = false;
    this.raised = false;
    this.tabindex = 0;

    this._boundKeypressHandler = this._keypressHandler.bind(this);
    this._boundFocusBlurHandler = this._focusBlurHandler.bind(this);
  }

  connectedCallback() {
    super.connectedCallback();

    window.addEventListener('keypress', this._boundKeypressHandler, true);
    this.addEventListener('focus', this._boundFocusBlurHandler, true);
    this.addEventListener('blur', this._boundFocusBlurHandler, true);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener('keypress', this._boundKeypressHandler,
        true);
  }

  _keypressHandler(event) {
    if (!this.focused) return;
    const keys = this.inputKeys || DEFAULT_INPUT_KEYS;
    const keyCode = event.keyCode;
    if (keys.includes(keyCode)) {
      this.click();
      event.preventDefault();
    }
  }

  _focusBlurHandler(event) {
    this.focused = event.type === 'focus';
  }
}
customElements.define('chops-button', ChopsButton);
