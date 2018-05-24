// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * '<cuic-view404>' is an error page for bad URLs etc.
 * @customElement
 * @polymer
 */
class View404 extends Polymer.Element {
  static get is() {
    return 'cuic-view404';
  }
  static get properties() {
    return {
      // This shouldn't be necessary, but the Analyzer isn't picking up
      // Polymer.Element#rootPath
      rootPath: String,
    };
  }
}

window.customElements.define(View404.is, View404);
