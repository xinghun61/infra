// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import './mr-day-icon.js';

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];
const WEEKDAY_ABBREVIATIONS = 'M T W T F S S'.split(' ');
const SECONDS_PER_DAY = 24 * 60 * 60;
// Only show comments from this many days ago and later.
const MAX_COMMENT_AGE = 31 * 3;

export class MrActivityTable extends LitElement {
  static get styles() {
    return css`
      :host {
        display: grid;
        grid-auto-flow: column;
        grid-auto-columns: repeat(13, auto);
        grid-template-rows: repeat(7, auto);
        margin: auto;
        width: 90%;
        text-align: center;
        line-height: 110%;
        align-items: center;
        justify-content: space-between;
      }
      :host[hidden] {
        display: none;
      }
    `;
  }

  render() {
    return html`
      ${WEEKDAY_ABBREVIATIONS.map((weekday) => html`<span>${weekday}</span>`)}
      ${this._weekdayOffset.map(() => html`<span></span>`)}
      ${this._activityArray.map((day) => html`
        <mr-day-icon
          .selected=${this.selectedDate === day.date}
          .commentCount=${day.commentCount}
          .date=${day.date}
          @click=${this._selectDay}
        ></mr-day-icon>
      `)}
    `;
  }

  static get properties() {
    return {
      comments: {type: Array},
      selectedDate: {type: Number},
    };
  }

  _selectDay(event) {
    const target = event.target;
    if (this.selectedDate === target.date) {
      this.selectedDate = undefined;
    } else {
      this.selectedDate = target.date;
    }

    this.dispatchEvent(new CustomEvent('dateChange', {
      detail: {
        date: this.selectedDate,
      },
    }));
  }

  get months() {
    const currentMonth = (new Date()).getMonth();
    return [MONTH_NAMES[currentMonth],
      MONTH_NAMES[currentMonth - 1],
      MONTH_NAMES[currentMonth - 2]];
  }

  get _weekdayOffset() {
    const startDate = new Date(this._activityArray[0].date * 1000);
    const startWeekdayNum = startDate.getDay()-1;
    const emptyDays = [];
    for (let i = 0; i < startWeekdayNum; i++) {
      emptyDays.push(' ');
    }
    return emptyDays;
  }

  get _todayUnixTime() {
    const now = new Date();
    const today = new Date(Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate(),
      24, 0, 0));
    const todayEndTime = today.getTime() / 1000;
    return todayEndTime;
  }

  get _activityArray() {
    const todayUnixEndTime = this._todayUnixTime;
    const comments = this.comments || [];

    const activityArray = [];
    for (let i = 0; i < MAX_COMMENT_AGE; i++) {
      const arrayDate = (todayUnixEndTime - ((i) * SECONDS_PER_DAY));
      activityArray.unshift({
        commentCount: 0,
        date: arrayDate,
      });
    }

    for (let i = 0; i < comments.length; i++) {
      const commentAge = Math.floor(
        (todayUnixEndTime - comments[i].timestamp) / SECONDS_PER_DAY);
      if (commentAge < MAX_COMMENT_AGE) {
        const pos = MAX_COMMENT_AGE - commentAge - 1;
        activityArray[pos].commentCount++;
      }
    }

    return activityArray;
  }
}
customElements.define('mr-activity-table', MrActivityTable);
