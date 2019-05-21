// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {html} from '@polymer/polymer/lib/utils/html-tag.js';
import {PolymerElement} from '@polymer/polymer/polymer-element.js';
import './mr-day-icon.js';

export class MrActivityTable extends PolymerElement {
  static get template() {
    return html`
      <style>
        :host {
          display: grid;
          /* 8 columns = 7 days of the week + 1 column to label the week */
          grid-auto-flow: column;
          grid-auto-columns: auto auto auto auto auto auto auto auto auto auto auto auto auto;
          grid-template-rows: auto auto auto auto auto auto auto;
          margin: auto;
          width: 90%;
          text-align: center;
          line-height: 110%;
          justify-items: center;
          min-height: 30%;
        }
        :host[hidden] {
          display: none;
        }
        span {
          font-size: 10px;
          place-self: center;
        }
      </style>

      <template is="dom-repeat" items="[[daysOfWeek]]">
        <span>[[item]]</span>
      </template>
      <template is="dom-repeat" items="[[startWeekday]]">
        <span></span>
      </template>
      <template is="dom-repeat" items="[[activityArray]]" as="day">
        <mr-day-icon activity-level="[[day.activityNum]]" on-tap="_onDaySelected" selected="[[_computeIsSelected(selectedDate, day.date)]]" commits="[[day.commits]]" comments="[[day.comments]]" date="[[day.date]]">
        </mr-day-icon>
      </template>
    `;
  }

  static get is() {
    return 'mr-activity-table';
  }

  static get properties() {
    return {
      user: {
        type: String,
      },
      viewedUserId: {
        type: Number,
      },
      commits: {
        type: Array,
      },
      comments: {
        type: Array,
      },
      startWeekday: {
        type: Array,
      },
      todayUnixEndTime: {
        type: Number,
        value: () => {
          const now = new Date();
          const today = new Date(Date.UTC(
            now.getUTCFullYear(),
            now.getUTCMonth(),
            now.getUTCDate(),
            24, 0, 0));
          const todayEndTime = today.getTime() / 1000;
          return todayEndTime;
        },
      },
      daysOfWeek: {
        type: Array,
        value: () => {
          return 'M T W T F S S'.split(' ');
        },
      },
      activityArray: {
        type: Array,
        reflectToAttribute: true,
        computed: 'computeActivityArray(commits, comments, todayUnixEndTime)',
        observer: '_computeWeekdayStart',
      },
      months: {
        type: Array,
        value: () => {
          const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
          const now = new Date();
          return [monthNames[now.getMonth()],
            monthNames[now.getMonth() - 1],
            monthNames[now.getMonth() - 2]];
        },
      },
      selectedDate: {
        type: Number,
        notify: true,
      },
    };
  }

  _computeIsSelected(day, itemDay) {
    return this.selectedDate == itemDay;
  }

  _onDaySelected(event) {
    if (this.selectedDate == event.target.date) {
      this.selectedDate = undefined;
    } else {
      this.selectedDate = event.target.date;
    }
  }

  _computeWeekdayStart() {
    const startDate = new Date(this.activityArray[0].date * 1000);
    const startWeekdayNum = startDate.getDay()-1;
    const emptyDays = [];
    for (let i = 0; i < startWeekdayNum; i++) {
      emptyDays.push(' ');
    }
    this.startWeekday = emptyDays;
  }

  _getTodayUnixTime() {
    const now = new Date();
    const today = new Date(Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate(),
      24, 0, 0));
    const todayEndTime = today.getTime() / 1000;
    return todayEndTime;
  }

  computeActivityArray(commits, comments, todayUnixEndTime) {
    if (!todayUnixEndTime) {
      return [];
    }
    commits = commits || [];
    comments = comments || [];

    const activityArray = [];
    for (let i = 0; i < 93; i++) {
      const arrayDate = (todayUnixEndTime - ((i) * 86400));
      activityArray.push({
        commits: 0,
        comments: 0,
        activityNum: 0,
        date: arrayDate,
      });
    }

    for (let i = 0; i < commits.length; i++) {
      const day = Math.floor((todayUnixEndTime - commits[i].commitTime) / 86400);
      if (day > 92) {
        break;
      }
      activityArray[day].commits++;
      activityArray[day].activityNum++;
    }

    for (let i = 0; i < comments.length; i++) {
      const day = Math.floor((todayUnixEndTime - comments[i].timestamp) / 86400);
      if (day > 92) {
        break;
      }
      activityArray[day].comments++;
      activityArray[day].activityNum++;
    }
    activityArray.reverse();
    return activityArray;
  }
}
customElements.define(MrActivityTable.is, MrActivityTable);
