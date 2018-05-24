// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * '<cuic-selector-set>' fetches the current filters and tags when created
 * @customElement
 */
class SelectorSet extends ElementBaseWithUrls {

  static get is() {
    return 'cuic-selector-set';
  }
  static get properties() {
    return {
      taglist: {
        type: Object,
        notify: true,
        value() { return {}; }
    }};
  }

  handleError_(e) {
    alert('Error fetching list of screenshot tags.')
    console.log('Error received fetching tags');
    console.log(e.detail);
  }

  handleResponse_(r) {
    this.dispatchEvent(new CustomEvent('tag-change'));
  }
}

window.customElements.define(SelectorSet.is, SelectorSet);
