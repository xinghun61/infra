// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Page that prompts the user for the location of the screenshot description
 * file.
 * @customElement
 * @polymer
 */
class SetScreenshotSource extends Polymer.Element {
  static get is() {
    return 'cuic-set-screenshot-source';
  }

  static get properties() {
    return {
      queryParams_: Object,
      value_: String,
    };
  }

  ready(){
    super.ready();
    this.$.url_form.addEventListener('submit', e => {
      e.preventDefault();
      this.set('queryParams_.screenshot_source', this.$.url_input.value);
    });
  }
}

window.customElements.define(SetScreenshotSource.is, SetScreenshotSource);
