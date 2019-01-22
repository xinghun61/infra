// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is govered by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

'use strict';

/**
 * `<chops-checkbox>`
 *
 * A checkbox component. This component is primarily a wrapper
 * around a native checkbox to allow easy sharing of styles.
 *
 */
class ChopsCheckbox extends Polymer.Element {
  static get is() {
    return 'chops-checkbox';
  }

  static get properties() {
    return {
      label: String,
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
        observer: '_checkedChange',
      },
    };
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
customElements.define(ChopsCheckbox.is, ChopsCheckbox);
