// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {prpcClient} from 'prpc-client-instance.js';
import './chops-chart.js';

const DEFAULT_NUM_DAYS = 30;
const CHART_OPTIONS = {
  animation: false,
  responsive: true,
  title: {
    display: true,
    text: 'Issues over time',
  },
  tooltips: {
    mode: 'index',
    intersect: false,
  },
  hover: {
    mode: 'nearest',
    intersect: true,
  },
  scales: {
    xAxes: [{
      display: true,
      scaleLabel: {
        display: true,
        labelString: 'Day',
      },
    }],
    yAxes: [{
      display: true,
      ticks: {
        beginAtZero: true,
      },
      scaleLabel: {
        display: true,
        labelString: 'Value',
      },
    }],
  },
};

export default class MrChart extends LitElement {
  static get properties() {
    return {
      progress: {type: Number},
      projectName: {type: String},
      indices: {type: Array},
      values: {type: Array},
      unsupportedFields: {type: Array},
      searchLimitReached: {type: Boolean},
    };
  }

  static get styles() {
    return css`
      :host {
        display: block;
        max-width: 800px;
        margin: 0 auto;
      }
      chops-chart {
        max-width: 100%;
      }
      div#options {
        max-width: 360px;
        margin: 2em auto;
        text-align: center;
      }
      div#options #unsupported-fields {
        font-weight: bold;
        color: orange;
      }
      p#search-limit-message {
        display: none;
        font-size: 1.25em;
        padding: 0.25em;
        background-color: var(--chops-orange-50);
      }
      progress {
        background-color: white;
        border: 1px solid #666;
        margin: 0 0 1em;
        width: 100%;
        visibility: visible;
      }
      ::-webkit-progress-bar {
        background-color: white;
      }
      progress::-webkit-progress-value {
        transition: width 1s;
        background-color: rgb(54, 162, 235);
      }
    `;
  }

  render() {
    const doneLoading = this.progress === 1;
    return html`
      <chops-chart
        type="line"
        .options=${CHART_OPTIONS}
        .data=${this._chartData(this.indices, this.values)}
      ></chops-chart>
      <div id="options">
        <p id="unsupported-fields">
          ${this.unsupportedFields.length ? `
            Unsupported fields: ${this.unsupportedFields.join(', ')}`: ''}
        </p>
        <progress
          value=${this.progress}
          ?hidden=${doneLoading}
        >Loading chart...</progress>
        <p id="search-limit-message" ?hidden=${!this.searchLimitReached}>
          Note: Some results are not being counted.
          Please narrow your query.
        </p>
        <label for="end-date">Choose end date:</label>
        <br />
        <input
          type="date"
          id="end-date"
          name="end-date"
          .value=${this.endDate && this.endDate.toISOString().substr(0, 10)}
          ?disabled=${!doneLoading}
          @change=${this._onEndDateChanged}
        />
      </div>
    `;
  }

  constructor() {
    super();
    this.progress = 0.05;
    this.values = [];
    this.indices = [];
    this.unsupportedFields = [];
    this.endDate = MrChart.getEndDate();
  }

  async connectedCallback() {
    super.connectedCallback();

    if (!this.projectName || !this.projectName.length) {
      throw new Error('Attribute `projectName` required.');
    }

    // Load Chart.js before chops-chart to allow data points to render as soon as
    // they are loaded.
    await import(/* webpackChunkName: "chartjs" */ 'chart.js/dist/Chart.min.js');

    this.dispatchEvent(new Event('chartLoaded'));
    this._fetchData(this.endDate);
  }

  _onEndDateChanged(e) {
    const value = e.target.value;
    this.endDate = MrChart.dateStringToDate(value);
    this._fetchData(this.endDate);

    const urlParams = MrChart.getSearchParams();

    // TODO(zhangtiff): Integrate with frontend routing once charts is part of the SPA.
    urlParams.set('end_date', value);
    const newUrl = `${location.protocol}//${location.host}${location.pathname}?${urlParams.toString()}`;
    window.history.pushState({}, '', newUrl);
  }

  async _fetchData(endDate) {
    // Reset chart variables except indices.
    this.progress = 0.05;

    let numTimestampsLoaded = 0;
    const timestampsChronological = MrChart.makeTimestamps(endDate);
    const tsToIndexMap = new Map(timestampsChronological.map((ts, idx) => (
      [ts, idx]
    )));
    this.indices = MrChart.makeIndices(timestampsChronological);
    const timestamps = MrChart.sortInBisectOrder(timestampsChronological);
    this.values = new Array(timestamps.length).fill(undefined);

    const fetchPromises = timestamps.map(async (ts) => {
      const data = await this._fetchDataAtTimestamp(ts);
      const index = tsToIndexMap.get(ts);
      this.values[index] = data.issues;
      numTimestampsLoaded += 1;
      const progressValue = numTimestampsLoaded / timestamps.length;
      this.progress = progressValue;

      return data;
    });

    const chartData = await Promise.all(fetchPromises);

    this.dispatchEvent(new Event('allDataLoaded'));

    // Check if the query includes any field values that are not supported.
    const flatUnsupportedFields = chartData.reduce((acc, datum) => {
      if (datum.unsupportedField) {
        acc = acc.concat(datum.unsupportedField);
      }
      return acc;
    }, []);
    this.unsupportedFields = Array.from(new Set(flatUnsupportedFields));

    this.searchLimitReached = chartData.some((d) => d.searchLimitReached);
  }

  _fetchDataAtTimestamp(timestamp) {
    return new Promise((resolve, reject) => {
      const params = MrChart.getSearchParams();
      const query = params.get('q');
      const cannedQuery = params.get('can');
      const message = {
        timestamp: timestamp,
        projectName: this.projectName,
        query: query,
        cannedQuery: cannedQuery,
      };
      const callPromise = prpcClient.call('monorail.Issues',
        'IssueSnapshot', message);
      return callPromise.then((response) => {
        resolve({
          date: timestamp * 1000,
          issues: response.snapshotCount[0].count || 0,
          unsupportedField: response.unsupportedField,
          searchLimitReached: response.searchLimitReached,
        });
      });
    });
  }

  _chartData(indices, values) {
    return {
      labels: indices,
      datasets: [{
        label: 'Issue count',
        backgroundColor: 'rgb(54, 162, 235)',
        borderColor: 'rgb(54, 162, 235)',
        data: values,
        fill: false,
      }],
    };
  }

  // Move first, last, and median to the beginning of the array, recursively.
  static sortInBisectOrder(timestamps) {
    const arr = [];
    if (timestamps.length === 0) {
      return arr;
    } else if (timestamps.length <= 2) {
      return timestamps;
    } else {
      const beginTs = timestamps.shift();
      const endTs = timestamps.pop();
      const medianTs = timestamps.splice(timestamps.length / 2, 1)[0];
      return [beginTs, endTs, medianTs].concat(
        MrChart.sortInBisectOrder(timestamps));
    }
  }

  // Populate array of timestamps we want to fetch.
  static makeTimestamps(endDate, numDays=DEFAULT_NUM_DAYS) {
    if (!endDate) {
      throw new Error('endDate required');
    }
    const endTimeSeconds = Math.round(endDate.getTime() / 1000);
    const secondsInDay = 24 * 60 * 60;
    const timestampsChronological = [];
    for (let i = 0; i < numDays; i++) {
      timestampsChronological.unshift(endTimeSeconds - (secondsInDay * i));
    }
    return timestampsChronological;
  }

  // Convert a string '2018-11-03' to a Date object.
  static dateStringToDate(dateString) {
    if (!dateString) {
      return null;
    }
    const splitDate = dateString.split('-');
    const year = Number.parseInt(splitDate[0]);
    // Month is 0-indexed, so subtract one.
    const month = Number.parseInt(splitDate[1]) - 1;
    const day = Number.parseInt(splitDate[2]);
    return new Date(Date.UTC(year, month, day, 23, 59, 59));
  }

  // Return a URLSearchParams object. Separate method for stubbing.
  static getSearchParams() {
    // TODO(zhangtiff): Make this use page.js's queryParams object instead
    // of parsing URL params multuple times, once charts is integrated with the SPA.
    return new URLSearchParams(document.location.search.substring(1));
  }

  // Returns a Date taken from end_date URL param, defaults to current date.
  static getEndDate() {
    const urlParams = MrChart.getSearchParams();
    if (urlParams.has('end_date')) {
      const date = MrChart.dateStringToDate(urlParams.get('end_date'));
      if (date) {
        return date;
      }
    }
    const today = new Date();
    today.setHours(23);
    today.setMinutes(59);
    today.setSeconds(59);
    return today;
  }

  static makeIndices(timestamps) {
    const dateFormat = {year: 'numeric', month: 'numeric', day: 'numeric'};
    return timestamps.map((ts) => (
      (new Date(ts * 1000)).toLocaleDateString('en-US', dateFormat)
    ));
  }
}

customElements.define('mr-chart', MrChart);
