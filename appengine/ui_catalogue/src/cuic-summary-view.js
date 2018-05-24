// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * '<cuic-summary-view>' is a summary view containing multiple filtered sets
* of screenshots.
 * @customElement
 * @polymer
 */
class SummaryView extends Polymer.Element {
  static get is() {
    return 'cuic-summary-view';
  }

  static get properties() {
    return {
      queryParams_: Object,
      selection_: Object,
    };
  }

  static get observers() {
    return [
      'readFilters_(queryParams_.selection)',
      'selectionChanged_(selection_.*)'
    ];
  }

  readFilters_(querySelection) {
    if (querySelection) {
      this.set('selection_', JSON.parse(querySelection));
    } else {
      this.set('selection_', {filters:{}, userTags:[]});
    }
  }

  selectionChanged_() {
    const newFilterString = JSON.stringify(this.selection_);
    if (!this.queryParams_.selection ||
      newFilterString !== this.queryParams_.selection) {
      this.set('queryParams_.selection', newFilterString);
    }
  }
}

window.customElements.define(SummaryView.is, SummaryView);
