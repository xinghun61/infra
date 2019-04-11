// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {standardTime, standardTimeShort} from './chops-timestamp-helpers';

/**
 * `<chops-timestamp>`
 *
 * This element shows a time in a human readable form.
 *
 * @customElement
 * @polymer
 */
export class ChopsTimestamp extends PolymerElement {
  static get template() {
    return html`
      [[_displayedTime]]
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
      /** Show the full timestamp on hover. */
      title: {
        type: String,
        reflectToAttribute: true,
        computed: '_renderFullTime(date)',
      },
      /** The Date object, which is stored in UTC, to be processed. */
      _date: {
        type: Object,
        computed: '_computeDate(timestamp)',
      },
      /** The displayed time. */
      _displayedTime: {
        type: String,
        computed: '_computeDisplayedTime(_date, short)',
      },
    };
  }

  _computeDate(timestamp) {
    let unixTimeMs = 0;
    // Make sure to do Date.parse before Number.parseInt because parseInt
    // will parse numbers within a string.
    if (/^\d+$/.test(timestamp)) {
      // Check if a string contains only digits before guessing it's
      // unix time. This is necessary because Number.parseInt will parse
      // number strings that contain non-numbers.
      unixTimeMs = Number.parseInt(timestamp) * 1000;
    } else {
      // Date.parse will parse strings with only numbers as though those
      // strings were truncated ISO formatted strings.
      unixTimeMs = Date.parse(timestamp);
      if (Number.isNaN(unixTimeMs)) {
        throw new Error('Timestamp is in an invalid format.');
      }
    }
    return new Date(unixTimeMs);
  }

  _computeDisplayedTime(date, short) {
    // TODO(zhangtiff): Add logic to dynamically re-compute relative time
    //   based on set intervals.
    if (!date) return;
    if (short) {
      return standardTimeShort(date);
    }
    return standardTime(date);
  }

  _renderFullTime(date) {
    return standardTime(date);
  }
}
customElements.define(ChopsTimestamp.is, ChopsTimestamp);
