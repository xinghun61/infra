// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

const ESC_KEYCODE = 27;

/**
 * `<chops-dialog>` displays a modal/dialog overlay.
 *
 * @customElement
 */
export class ChopsDialog extends LitElement {
  static get styles() {
    return css`
      :host {
        position: fixed;
        z-index: 9999;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        overflow: auto;
        background-color: rgba(0,0,0,0.4);
        display: flex;
        align-items: center;
        justify-content: center;
      }
      :host(:not([opened])), [hidden] {
        display: none;
        visibility: hidden;
      }
      :host([closeOnOutsideClick]),
      :host([closeOnOutsideClick]) .dialog::backdrop {
        /* TODO(zhangtiff): Deprecate custom backdrop in favor of native
        * browser backdrop.
        */
        cursor: pointer;
      }
      .dialog {
        background: none;
        border: 0;
        overflow: auto;
        max-width: 90%;
      }
      .dialog-content {
        /* This extra div is here because otherwise the browser can't
        * differentiate between a click event that hits the dialog element or
        * its backdrop pseudoelement.
        */
        box-sizing: border-box;
        background: white;
        padding: 1em 16px;
        cursor: default;
        box-shadow: 0px 3px 20px 0px hsla(0, 0%, 0%, 0.4);
        width: var(--chops-dialog-width);
        max-width: var(--chops-dialog-max-width, 100%);
      }
    `;
  }

  render() {
    return html`
      <dialog class="dialog" role="dialog" @cancel=${this._cancelHandler}>
        <div class="dialog-content">
          <slot></slot>
        </div>
      </dialog>
    `;
  }

  static get properties() {
    return {
      /**
       * Whether the dialog should currently be displayed or not.
       */
      opened: {
        type: Boolean,
        reflect: true,
      },
      /**
       * A boolean that determines whether clicking outside of the dialog
       * window should close it.
       */
      closeOnOutsideClick: {
        type: Boolean,
      },
      /**
       * A function fired when the element tries to change its own opened
       * state. This is useful if you want the dialog state managed outside
       * of the dialog instead of with internal state. (ie: with Redux)
       */
      onOpenedChange: {
        type: Object,
      },
      /**
       * Allow people to exit the dialog using keyboard shortcuts. Defaults
       * to the escape key.
       */
      exitKeys: {
        type: Array,
      },
      /**
       * When True, disables exiting keys and closing on outside clicks.
       * Forces the user to interact with the dialog rather than just dismissing
       * it.
       */
      forced: {
        type: Boolean,
      },
      _boundKeydownHandler: {
        type: Object,
      },
      _previousFocusedElement: {
        type: Object,
      },
    };
  }

  constructor() {
    super();

    this.opened = false;
    this.closeOnOutsideClick = false;
    this.exitKeys = [ESC_KEYCODE];
    this.forced = false;
    this._boundKeydownHandler = this._keydownHandler.bind(this);
  }

  connectedCallback() {
    super.connectedCallback();

    this.addEventListener('click', (evt) => {
      if (!this.opened || !this.closeOnOutsideClick || this.forced) return;

      const hasDialog = evt.composedPath().find(
        (node) => {
          return node.classList && node.classList.contains('dialog-content');
        }
      );
      if (hasDialog) return;

      this.close();
    });

    window.addEventListener('keydown', this._boundKeydownHandler, true);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener('keydown', this._boundKeydownHandler,
      true);
  }

  updated(changedProperties) {
    if (changedProperties.has('opened')) {
      this._openedChanged(this.opened);
    }
  }

  _keydownHandler(event) {
    if (!this.opened) return;
    const keyCode = event.keyCode;

    // Handle closing hot keys.
    if (this.exitKeys.includes(keyCode) && !this.forced) {
      this.close();
    }
  }

  close() {
    if (this.onOpenedChange) {
      this.onOpenedChange(false);
    } else {
      this.opened = false;
    }
  }

  open() {
    if (this.onOpenedChange) {
      this.onOpenedChange(true);
    } else {
      this.opened = true;
    }
  }

  toggle() {
    this.opened = !this.opened;
  }

  _cancelHandler(evt) {
    if (!this.forced) {
      this.close();
    } else {
      evt.preventDefault();
    }
  }

  _getActiveElement() {
    // document.activeElement alone isn't sufficient to find the active
    // element within shadow dom.
    let active = document.activeElement || document.body;
    let activeRoot = active.shadowRoot || active.root;
    while (activeRoot && activeRoot.activeElement) {
      active = activeRoot.activeElement;
      activeRoot = active.shadowRoot || active.root;
    }
    return active;
  }

  _openedChanged(opened) {
    const dialog = this.shadowRoot.querySelector('dialog');
    if (opened) {
      // For accessibility, we want to ensure we remember the element that was
      // focused before this dialog opened.
      this._previousFocusedElement = this._getActiveElement();

      if (dialog.showModal) {
        dialog.showModal();
      } else {
        dialog.setAttribute('open', 'true');
      }
      if (this._previousFocusedElement) {
        this._previousFocusedElement.blur();
      }
    } else {
      if (dialog.close) {
        dialog.close();
      } else {
        dialog.setAttribute('open', undefined);
      }

      if (this._previousFocusedElement) {
        const element = this._previousFocusedElement;
        requestAnimationFrame(() => {
          // HACK. This is to prevent a possible accessibility bug where
          // using a keypress to trigger a button that exits a modal causes
          // the modal to immediately re-open because the button that
          // originally opened the modal refocuses, and the keypress
          // propagates.
          element.focus();
        });
      }
    }
  }
}

customElements.define('chops-dialog', ChopsDialog);
