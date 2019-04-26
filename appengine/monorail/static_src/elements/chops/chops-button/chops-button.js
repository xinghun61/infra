// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

/**
 * `<chops-button>` displays a styled button component with a few niceties.
 *
 * @customElement
 * @polymer
 * @demo /demo/chops-button_demo.html
 */
export class ChopsButton extends PolymerElement {
  static get template() {
    return html`
      <style>
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
      </style>
      <slot></slot>
    `;
  }

  static get is() {
    return 'chops-button';
  }

  static get properties() {
    return {
      /** Whether the button is available for input or not. */
      disabled: {
        type: Boolean,
        reflectToAttribute: true,
      },
      /**
       * For accessibility. These are the keys that you can use to fire the
       * onclick event for chops-button. The value is an Array of
       * JavaScript key input codes, defaulting to space and enter keys.
       */
      inputKeys: {
        type: Array,
        value: [13, 32],
      },
      /**
       * If true, the element currently has focus. Changed through focus
       * and blur event listeners.
       */
      focused: {
        type: Boolean,
        value: false,
        reflectToAttribute: true,
      },
      /** Whether the button should have a shadow or not. */
      raised: {
        type: Boolean,
        value: false,
        reflectToAttribute: true,
      },
      /** Used for accessibility to state this component is a button. **/
      role: {
        type: String,
        value: 'button',
        reflectToAttribute: true,
      },
      /** Causes the button to be focusable for accessbility. **/
      tabindex: {
        type: Number,
        value: 0,
        reflectToAttribute: true,
      },
      _boundKeypressHandler: {
        type: Function,
        value: function() {
          return this._keypressHandler.bind(this);
        },
      },
      _boundFocusBlurHandler: {
        type: Function,
        value: function() {
          return this._focusBlurHandler.bind(this);
        },
      },
    };
  }

  ready() {
    super.ready();
    this.addEventListener('focus', this._boundFocusBlurHandler, true);
    this.addEventListener('blur', this._boundFocusBlurHandler, true);
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener('keypress', this._boundKeypressHandler, true);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener('keypress', this._boundKeypressHandler,
      true);
  }

  _keypressHandler(event) {
    if (!this.focused) return;
    const keyCode = event.keyCode;
    if (this.inputKeys.includes(keyCode)) {
      this.click();
    }
  }

  _focusBlurHandler(event) {
    this.focused = event.type === 'focus';
  }
}
customElements.define(ChopsButton.is, ChopsButton);
