// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

/**
 * `<chops-checkbox>`
 *
 * A checkbox component. This component is primarily a wrapper
 * around a native checkbox to allow easy sharing of styles.
 *
 */
export class ChopsCheckbox extends LitElement {
  static get styles() {
    return css`
      :host {
        --chops-checkbox-color: var(--chops-primary-accent-color);
        /* A bit brighter than Chrome's default focus color to
        * avoid blending into the checkbox's blue. */
        --chops-checkbox-focus-color: hsl(193, 82%, 63%);
        --chops-checkbox-size: 16px;
        --chops-checkbox-check-size: 18px;
      }
      label {
        cursor: pointer;
        display: inline-flex;
        align-items: center;
      }
      input[type="checkbox"] {
        /* We need the checkbox to be hidden but still accessible. */
        opacity: 0;
        width: 0;
        height: 0;
        position: absolute;
        top: -9999;
        left: -9999;
      }
      label::before {
        width: var(--chops-checkbox-size);
        height: var(--chops-checkbox-size);
        margin-right: 8px;
        box-sizing: border-box;
        content: "\\2713";
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: 2px solid #222;
        border-radius: 2px;
        background: #fff;
        font-size: var(--chops-checkbox-check-size);
        padding: 0;
        color: transparent;
      }
      input[type="checkbox"]:focus + label::before {
        /* Make sure an outline shows around this element for
        * accessibility.
        */
        box-shadow: 0 0 5px 1px var(--chops-checkbox-focus-color);
      }
      input[type="checkbox"]:checked + label::before {
        background: var(--chops-checkbox-color);
        border-color: var(--chops-checkbox-color);
        color: #fff;
      }
    `;
  }

  render() {
    return html`
      <!-- Note: Avoiding 2-way data binding to futureproof this code
        for LitElement. -->
      <input id="checkbox" type="checkbox" ?checked=${this.checked} @change=${this._checkedChangeHandler}>
      <label for="checkbox">
        <slot></slot>
      </label>
    `;
  }

  static get properties() {
    return {
      label: {
        type: String,
      },
      /**
       * Note: At the moment, this component does not manage its own
       * internal checked state. It expects its checked state to come
       * from its parent, and its parent is expected to update the
       * chops-checkbox's checked state on a change event.
       *
       * This can be generalized in the future to support multiple
       * ways of managing checked state if needed.
       **/
      checked: {
        type: Boolean,
      },
    };
  }

  update(changedProperties) {
    if (changedProperties.has('checked')) {
      this._checkedChange(this.checked);
    }
    super.update(changedProperties);
  }

  click() {
    super.click();
    this.shadowRoot.querySelector('#checkbox').click();
  }

  _checkedChangeHandler(evt) {
    this._checkedChange(evt.target.checked);
  }

  _checkedChange(checked) {
    if (checked === this.checked) return;
    const customEvent = new CustomEvent('checked-change', {
      detail: {
        checked: checked,
      },
    });
    this.dispatchEvent(customEvent);
  }
}
customElements.define('chops-checkbox', ChopsCheckbox);
