// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html} from 'lit-element';

import {store, connectStore} from 'elements/reducers/base.js';
import * as user from 'elements/reducers/user.js';
import 'elements/chops/chops-toggle/chops-toggle.js';

/**
 * `<mr-code-font-toggle>`
 *
 * Code font toggle button for the issue detail page.  Pressing it
 * causes issue description and comment text to switch to monospace
 * font and the setting is saved in the user's preferences.
 */
export class MrCodeFontToggle extends connectStore(LitElement) {
  render() {
    return html`
      <chops-toggle
        ?checked=${this._codeFont}
        ?disabled=${this._prefsInFlight}
        @checked-change=${this._toggleFont}
        title="Code font"
       >Code</chops-toggle>
    `;
  }

  static get properties() {
    return {
      prefs: {type: Object},
      userDisplayName: {type: String},
      initialValue: {type: Boolean},
      _prefsInFlight: {type: Boolean},
    };
  }

  stateChanged(state) {
    this.prefs = user.prefs(state);
    this._prefsInFlight = user.requests(state).fetchPrefs.requesting
      || user.requests(state).setPrefs.requesting;
  }

  constructor() {
    super();
    this.initialValue = false;
    this.userDisplayName = '';
  }

  get _codeFont() {
    const {prefs, initialValue} = this;
    if (!prefs) return initialValue;
    return prefs.get('code_font') === 'true';
  }

  _toggleFont(e) {
    const checked = e.detail.checked;
    this.dispatchEvent(new CustomEvent('font-toggle', {detail: {checked}}));

    const newPrefs = [{name: 'code_font', value: '' + checked}];
    store.dispatch(user.setPrefs(newPrefs, !!this.userDisplayName));
  }
}
customElements.define('mr-code-font-toggle', MrCodeFontToggle);
