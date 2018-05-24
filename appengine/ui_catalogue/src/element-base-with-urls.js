// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Base for classes that need the URLs of images and data. The methods can't
 * simply be functions, since Polymer computed binding binds to methods
 */
class ElementBaseWithUrls extends Polymer.Element {

  screenshotLocationParam_() {
    return {
      'screenshot_source': this.screenshotSource_(),
    };
  }

  computeScreenshotUrl_(key) {
    const queryString = window.encodeURIComponent('screenshot_source') + '=' +
        window.encodeURIComponent(this.screenshotSource_())
    return this.resolveUrl('/service/' + key + '/image') + '?' + queryString;
  }

  // Added so that it can be overridden for testing
  get locationUrl_() {
    return new URL(document.location);
  }

  screenshotSource_() {
    const params = this.locationUrl_.searchParams;
    return params.get('screenshot_source');
  }

  computeDataUrl_(key) {
    // If the key is empty or null, clear the URL so that iron-ajax doesn't
    // make the request. This is needed because iron-ajax will otherwise
    // repeat the request when the key is cleared, which happens when we
    // switch back to the summary page.
    if (!key) return '';
    return '/service/' + key + '/data';
  }

}
