// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * A '<cuic-screenshot-strip>' displays a filtered set of screenshots.
 *
 * The element includes menus for filtering the screenshots, and the resultant
 * screenshots.
 * @customElement
 * @polymer
 */
class ScreenshotStrip extends Polymer.Element {
  static get is() {
    return 'cuic-screenshot-strip';
  }

  static get properties() {
    return {
      screenshots_: {
        type: Array,
        value: function() {
          return [];
        }
      },
      selection: {type: Object, notify: true},
    };
  }

  static get observers() {
    return ['selectionChanged_(selection.*)'];
  }

  sortArray_(array, f) {
    array.sort((a,b) => {
      const fa = f(a);
      const fb = f(b);
      if (fa < fb) return -1;
      if (fa > fb) return 1;
      return 0;
    });
  }

  selectionChanged_(filters) {
    if (filters) {
      this.$.screenshots.requestScreenshotsForSelector(filters.base);
    }
  }

  handleScreenshotsReceived_(event) {
    if (event.detail) {
      this.sortArray_(event.detail, s => s.label.toUpperCase());
      this.set('screenshots_', event.detail);
    }
  }

  display_(item) {
    return item.values.length > 1;
  }
}

window.customElements.define(ScreenshotStrip.is, ScreenshotStrip);
