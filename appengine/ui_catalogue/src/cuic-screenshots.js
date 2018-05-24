// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
 * '<cuic-screenshots>' is a pure data element for accessing the screenshot set.
 * @customElement
 */
class Screenshots extends ElementBaseWithUrls {
  /**
   * @typedef {Object} Screenshot a description of a screenshot.
   * @property {!string} location the location of the image.
   * @property {!string} label a human readable label for the screenshot.
   */

  static get is() {
    return 'cuic-screenshots';
  }
  /**
   * Return the screenshots that match a selector.
   *
   *@param {filters: !Object<string, string>, tags: !string[]} selector
   */
  requestScreenshotsForSelector(selector) {
    if (!this.screenshotSource_()) return;
    this.$['get-screenshot-list'].params = Object.assign(
        {
          filters: JSON.stringify(selector.filters),
          userTags: selector.userTags
        },
        this.screenshotLocationParam_());
    this.$['get-screenshot-list'].generateRequest();
  }

  /**
   * Event handler for the response. The response is an array of Screenshots
   */
  handleScreenshotListResponse_(event) {
    this.dispatchEvent(
        new CustomEvent('screenshots-received',
            {detail: event.detail.response}));
  }

  handleScreenshotListError_(e) {
    alert('Error fetching screenshot list.')
    console.log('Error received fetching screenshot list');
    console.log(e.detail);
  }
}


window.customElements.define(Screenshots.is, Screenshots);
