// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html} from 'lit-element';

import {standardTime, standardTimeShort} from './chops-timestamp-helpers';

/**
 * `<chops-timestamp>`
 *
 * This element shows a time in a human readable form.
 *
 * @customElement
 */
export class ChopsTimestamp extends LitElement {
  render() {
    return html`
      ${this._displayedTime}
    `;
  }

  static get properties() {
    return {
      /** The data for the time which can be in any format readable by
       *  Date.parse.
       */
      timestamp: {type: String},
      /** When true, a shorter version of the date will be displayed. */
      short: {type: Boolean},
      /**
       * The Date object, which is stored in UTC, to be converted to a string.
      */
      _date: {type: Object},
    };
  }

  get _displayedTime() {
    const date = this._date;
    const short = this.short;
    // TODO(zhangtiff): Add logic to dynamically re-compute relative time
    //   based on set intervals.
    if (!date) return;
    if (short) {
      return standardTimeShort(date);
    }
    return standardTime(date);
  }

  update(changedProperties) {
    if (changedProperties.has('timestamp')) {
      this._date = this._parseTimestamp(this.timestamp);
      this.setAttribute('title', standardTime(this._date));
    }
    super.update(changedProperties);
  }

  _parseTimestamp(timestamp) {
    if (!timestamp) return;

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
}
customElements.define('chops-timestamp', ChopsTimestamp);
