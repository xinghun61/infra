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
      <chops-toggle
         checked="[[checked]]"
         on-checked-change="_checkedChangeHandler"
       >Code</chops-toggle>
    `;
  }

  static get is() {
    return 'mr-code-font-toggle';
  }

  static get properties() {
    return {
      checked: {
        type: Boolean,
        observer: '_checkedChange',
      },
    };
  }

  _checkedChangeHandler(evt) {
    this._checkedChange(evt.detail.checked);
  }

  _checkedChange(checked) {
    if (checked === this.checked) return;
    const cursorArea = document.querySelector('#cursorarea');
    if (cursorArea && window.prpcClient) {
      this.checked = checked;
      if (checked) {
        cursorArea.classList.add('codefont');
      } else {
        cursorArea.classList.remove('codefont');
      }
      const message = {
          prefs: [{name: 'code_font', value: '' + checked}],
      };
      const setPrefsCall = window.prpcClient.call(
          'monorail.Users', 'SetUserPrefs', message);
      setPrefsCall.then((resp) => {
         // successfully saved prefs
      }).catch((reason) => {
        console.error('SetUserPrefs failed: ' + reason);
      });
    }
  }
}
customElements.define(MrCodeFontToggle.is, MrCodeFontToggle);
