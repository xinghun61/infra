// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import '@polymer/paper-icon-button/paper-icon-button.js';
import '@polymer/iron-icons/iron-icons.js';
import {html} from '@polymer/polymer/lib/utils/html-tag.js';
import {PolymerElement} from '@polymer/polymer/polymer-element.js';


const WEEK_SPAN = 7;

/**
 * `<table-footer>`
 *
 * Holds the controls for scrolling through weeks of the status table.
 */
class TableFooter extends PolymerElement {
  static get template() {
    return html`
      <style>
        .foot {
          border-color: rgba(0, 0, 0, .7);
          border-top: 1px solid;
          color: rgba(0, 0, 0, .7);
          font-size: .75em;
          font-weight: normal;
          height: 55px;
          padding: 0 14px 0 0;
        }

        .foot paper-icon-button {
          height: 24px;
          margin-left: 24px;
          padding: 0;
          width: 24px;
        }
        .hidden,
        .not-shown {
          display: none;
        }
        .not-hidden,
        .shown {
          display: inline-block;
        }
      </style>
      <div>
        <paper-icon-button class$="[[prevButtonClass]]"
            icon="chevron-left" on-tap="_goToPrevPage"></paper-icon-button>
        <paper-icon-button class$="not-[[prevButtonClass]]"
            icon="chevron-left" disabled on-tap="_goToPrevPage"></paper-icon-button>
        <paper-icon-button class$="[[nextButtonClass]]"
            icon="chevron-right" on-tap="_goToNextPage"></paper-icon-button>
        <paper-icon-button class$="not-[[nextButtonClass]]"
            icon="chevron-right" disabled on-tap="_goToNextPage"></paper-icon-button>
      </div>
    `;
  }

  static get is() { return 'table-footer'; }

  ready() {
    super.ready();
  }

  static get properties() {
    return {
      latestDate: {
        type: Number,
        notify: true,
      },
      tsNext: {
        type: Number,
        computed:'_computeTsNext(latestDate)',
      },
      tsPrev: {
        type: Number,
        computed: '_computeTsPrev(latestDate)',
      },
      prevButtonClass: {
        type: String,
        value: 'hidden',
        computed: '_computePrevButtonClass(tsPrev)',
      },
      nextButtonClass: {
        type: String,
        value: 'hidden',
        computed: '_computeNextButtonClass(tsNext)',
      },
    }
  }

  /**
   * This calculates the timestamp of the previous week's last date. The
   * timestamp returned will be undefined if the current week being viewed is
   * the very first week that this dashboard started collecting data. If the
   * latestDate is within the second week the previous timestamp will be set to
   * endOfFirstWeek.
   */
  _computeTsPrev(latestDate) {
    // Wednesday, May 24, 2017 12:00:00 AM GMT
    const endOfFirstWeek = 1495584000000;
    const endOfSecondWeek = 1496275199000;
    const dateCenterLocal = new Date(latestDate);
    let prev;
    if (latestDate > endOfFirstWeek && latestDate <= endOfSecondWeek) {
      prev = endOfFirstWeek;
    } else if (latestDate > endOfSecondWeek) {
      prev = this._getTimeStamps(dateCenterLocal, -WEEK_SPAN);
    }
    return prev;
  }

   /**
    * This calculates the timestamp of the next week's last date. If the
    * latestDate is the current date then there should be no link for the next
    * button so the timestamp return should be undefined.
    */
  _computeTsNext(latestDate) {
    let dateCenterLocal = new Date(latestDate);
    let next;
    if (!this._isSameDay(dateCenterLocal, new Date())) {
      next = this._getTimeStamps(dateCenterLocal, WEEK_SPAN);
    }
    return next;
  }

  _computePrevButtonClass(tsPrev) {
    return tsPrev ? 'shown' : 'hidden';
  }

  _computeNextButtonClass(tsNext) {
    return tsNext ? 'shown' : 'hidden';
  }

  _goToPrevPage() {
    this.latestDate = this.tsPrev;
  }

  _goToNextPage() {
    this.latestDate = this.tsNext;
  }

  _getTimeStamps(baseDate, diff) {
    let date = new Date(baseDate);
    date.setDate(date.getDate() + diff);
    // A link should never take the user to a page showing days that haven't
    // happened yet.
    if (date > new Date()) {
      date = new Date();
    }
    return date.setHours(23, 59, 59, 0);
  }

  /**
   * isSameDay should be used to check if two Date objects occur within
   * the same day. Simply comparing the two objects would be too granular
   * as Date objects also include the time within a day.
   * @param {Date} dateOne - The first date to be compared.
   * @param {Date} dateTwo - The other date to be compared.
   */
  _isSameDay(dateOne, dateTwo) {
    return dateOne.getFullYear() === dateTwo.getFullYear() &&
    dateOne.getMonth() === dateTwo.getMonth() &&
    dateOne.getDate() === dateTwo.getDate();
  }
}
customElements.define(TableFooter.is, TableFooter);
