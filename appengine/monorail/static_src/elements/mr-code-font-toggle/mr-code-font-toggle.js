// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../chops/chops-toggle/chops-toggle.js';

/**
 * `<mr-code-font-toggle>`
 *
 * Code font toggle button for the issue detail page.  Pressing it
 * causes issue description and comment text to switch to monospace
 * font and the setting is saved in the user's preferences.
 */
export class MrCodeFontToggle extends PolymerElement {
  static get template() {
    return html`
      <chops-toggle on-checked-change="_checkedChangeHandler">Code</chops-toggle>
    `;
  }

  static get is() {
    return 'mr-code-font-toggle';
  }

  _checkedChangeHandler(evt) {
    this._checkedChange(evt.detail.checked);
  }

  _checkedChange(checked) {
    let cursorArea = document.querySelector('#cursorarea');
    if (checked) {
      cursorArea.classList.add('codefont');
    } else {
      cursorArea.classList.remove('codefont');
    }
    // TODO(jrobbins): Use pRPC call to store pref on the server.
  }
}
customElements.define(MrCodeFontToggle.is, MrCodeFontToggle);
