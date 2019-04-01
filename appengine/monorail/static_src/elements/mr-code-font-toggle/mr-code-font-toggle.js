// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {ReduxMixin} from '../redux/redux-mixin.js';
import * as user from '../redux/user.js';
import '../chops/chops-toggle/chops-toggle.js';

/**
 * `<mr-code-font-toggle>`
 *
 * Code font toggle button for the issue detail page.  Pressing it
 * causes issue description and comment text to switch to monospace
 * font and the setting is saved in the user's preferences.
 */
export class MrCodeFontToggle extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <chops-toggle
         checked="[[_codeFont]]"
         on-checked-change="_checkedChangeHandler"
       >Code</chops-toggle>
    `;
  }

  static get is() {
    return 'mr-code-font-toggle';
  }

  static get properties() {
    return {
      prefs: Object,
      userDisplayName: String,
      initialValue: {
        type: Boolean,
        value: false,
      },
      _codeFont: {
        type: Boolean,
        computed: '_computeCodeFont(prefs, initialValue)',
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      prefs: user.user(state).prefs,
    };
  }

  _computeCodeFont(prefs, initialValue) {
    if (!prefs) return initialValue;
    return prefs.get('code_font') === 'true';
  }

  fetchPrefs() {
    this.dispatchAction(user.fetchPrefs());
  }

  _checkedChangeHandler(e) {
    const checked = e.detail.checked;
    this.dispatchEvent(new CustomEvent('font-toggle', {detail: {checked}}));
    if (this.userDisplayName) {
      const message = {
        prefs: [{name: 'code_font', value: '' + checked}],
      };
      const setPrefsCall = window.prpcClient.call(
        'monorail.Users', 'SetUserPrefs', message);
      setPrefsCall.then((resp) => {
        this.fetchPrefs();
      }).catch((reason) => {
        console.error('SetUserPrefs failed: ' + reason);
      });
    } else {
      const newPrefs = new Map(this.prefs);
      newPrefs.set('code_font', '' + checked);
      this.dispatchAction(user.setPrefs(newPrefs));
    }
  }
}
customElements.define(MrCodeFontToggle.is, MrCodeFontToggle);
