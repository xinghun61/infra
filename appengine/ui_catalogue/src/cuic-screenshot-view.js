// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * '<cuic-screenshot-view>' displays a details of a single screenshot.
 *
 * @customElement
 * @polymer
 */
class ScreenshotView extends ElementBaseWithUrls {
  static get is() {
    return 'cuic-screenshot-view';
  }
  static get properties() {
    return {
      key: {
        type: String,
        observer: 'keyChanged_'
      },
      filterValues_: Array,
      userTags_: Array,
      metadata_: Array,
    };
  }

  keyChanged_() {
    if (this.key) {
      this.$['get-screenshot-data'].generateRequest();
    }
  }

  handleError_(e) {
    alert('Error fetching screenshot data.')
    console.log('Error fetching screenshot data:');
    console.log(e.detail);
  }

  convertToArray_(o) {
    return Object.entries(o).map(
        e=>{ return {'name': e[0], 'value': e[1]}});
  }

  handleResponse_(r) {
    const response = r.detail.response;
    this.set('filterValues_', this.convertToArray_(response.filters));
    this.set('metadata_', this.convertToArray_(response.metadata));
    this.set('userTags_', response.userTags)
  }
}


window.customElements.define(ScreenshotView.is, ScreenshotView);
