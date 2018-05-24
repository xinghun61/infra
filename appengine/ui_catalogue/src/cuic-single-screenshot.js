// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * '<cuic-single-screenshot>' is an element containing a screenshot and its
 * title within the summary page.
 * @customEleemnt
 * @polymer
 */
class SingleScreenshot extends ElementBaseWithUrls {
  static get is() {
    return 'cuic-single-screenshot';
  }
  static get properties() {
    return {
      label: String,
      key: String,
      queryParams_: Object,
      query_:String,
    };
  }
  computeLink_(key, queryParams) {
    if (!queryParams) return null;
    return this.resolveUrl('/cuic-screenshot-view?screenshot_source=' +
        queryParams.screenshot_source + '&key=' + key);
  }
}

window.customElements.define(SingleScreenshot.is, SingleScreenshot);