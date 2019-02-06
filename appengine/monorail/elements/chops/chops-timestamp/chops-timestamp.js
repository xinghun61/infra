// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '../../../node_modules/@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import moment from 'moment-timezone';

/**
 * `<chops-timestamp>` displays a formatted time string in PDT and the relative time.
 *
 * This element shows a time in a human readable form.
 *
 * @customElement
 * @polymer
 * @demo /demo/chops-timestamp_demo.html
 */
export class ChopsTimestamp extends PolymerElement {
  static get template() {
    return html`
      <template is="dom-if" if="[[!short]]">
        [[_formattedDate]] ([[_computeRelativeTime(_date)]])
      </template>
      <template is="dom-if" if="[[short]]" title="[[_formattedDate]]">
        [[_computeRelativeTime(_date)]]
      </template>
    `;
  }

  static get is() {
    return 'chops-timestamp';
  }

  static get properties() {
    return {
      /** The data for the time which can be in any format readable by
       *  Date.parse.
       */
      timestamp: String,
      /** When true, a shorter version of the date will be displayed. */
      short: {
        type: Boolean,
        value: false,
      },
      /** The format of the date. */
      dateFormat: {
        type: String,
        value: 'ddd, D MMM YYYY, h:mm a z',
      },
      /** The moment object, which is stored in UTC, to be processed. */
      _date: {
        type: Object,
        value: () => (moment()),
        computed: '_computeDate(timestamp)',
      },
      /** The formatted date. */
      _formattedDate: {
        type: String,
        computed: '_computeDisplayedTime(_date, dateFormat)',
      },
    };
  }

  _computeDate(timestamp) {
    // Check if timestamp is unix time first.
    let date = Number.parseInt(timestamp);
    if (Number.isNaN(date)) {
      // Date.parse returns milliseconds since epoch but we want seconds.
      date = Date.parse(timestamp) / 1000;
      if (Number.isNaN(date)) {
        // Default to now if all else fails.
        date = (new Date()).getTime() / 1000;
      }
    }

    return moment.unix(date).tz('America/Los_Angeles');
  }

  _computeDisplayedTime(date, format) {
    return date.format(format);
  }

  _computeRelativeTime(date) {
    return date.fromNow();
  }
}
customElements.define(ChopsTimestamp.is, ChopsTimestamp);
