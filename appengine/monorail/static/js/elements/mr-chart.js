// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '/deployed_node_modules/chart.js/dist/Chart.min.js';
import AutoRefreshPrpcClient from '../prpc.js';

const DEFAULT_NUM_DAYS = 30;

export default class MrChart extends HTMLElement {

  static is() {
    return 'mr-chart';
  }

  constructor() {
    super();
    this._animationFrameRequested = false;

    this.projectName = this.getAttribute('project-name');
    if (!this.projectName || !this.projectName.length) {
      throw new Error('Attribute `project-name` required.');
    }
    this.values = [];
    this.indices = [];

    // Set up DOM and initialize chart onto canvas.
    const shadowRoot = this.attachShadow({mode: 'open'});
    shadowRoot.appendChild(this._template().content.cloneNode(true));
    const ctx = shadowRoot.getElementById('canvas').getContext('2d');
    this.chart = new window.Chart(ctx, this._chartConfig(this.indices, this.values));
    this.progressBar = shadowRoot.querySelector('progress');
    this.endDateInput = shadowRoot.getElementById('end-date');
    this.unsupportedFieldsEl = shadowRoot.getElementById('unsupported-fields');
    this.searchLimitEl = shadowRoot.getElementById('search-limit-message');

    // Set up pRPC client.
    this.prpcClient = new AutoRefreshPrpcClient(
      window.CS_env.token, window.CS_env.tokenExpiresSec);

    // Get initial date.
    const endDate = MrChart.getEndDate();
    this.endDateInput.value = endDate.toISOString().substr(0, 10);

    this.endDateInput.addEventListener('change', (e) => {
      const newEndDate = MrChart.dateStringToDate(e.target.value);
      this._fetchData(newEndDate);

      const urlParams = MrChart.getSearchParams();
      urlParams.set('end_date', this.endDateInput.value);
      const newUrl = `${location.protocol}//${location.host}${location.pathname}?${urlParams.toString()}`;
      window.history.pushState({}, '', newUrl);
    });

    this._fetchData(endDate);
  }

  _updateChartValues() {
    if (this._animationFrameRequested) {
      return;
    }

    this._animationFrameRequested = true;
    window.requestAnimationFrame(() => {
      this.chart.data.datasets[0].data = this.values;
      this.chart.data.labels = this.indices;
      this.chart.update();

      if (this.progressBar.value === 1) {
        this.progressBar.style.visibility = 'hidden';
        this.endDateInput.disabled = false;
      } else {
        this.progressBar.style.visibility = 'visible';
        this.endDateInput.disabled = true;
      }

      this._animationFrameRequested = false;
    });
  }

  async _fetchData(endDate) {
    // Reset chart variables except indices.
    this.progressBar.value = 0.05;

    // Render blank chart.
    this._updateChartValues();

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
      this.progressBar.setAttribute('value', progressValue);
      this.progressBar.style.setProperty('--value', progressValue + '%');

      this._updateChartValues();
      return data;
    });

    const chartData = await Promise.all(fetchPromises);
    this.dispatchEvent(new Event('allDataLoaded'));

    const flatUnsupportedFields = chartData.reduce((acc, datum) => {
      if (datum.unsupportedField) {
        acc = acc.concat(datum.unsupportedField);
      }
      return acc;
    }, []);
    const uniqueUnsupportedFields = Array.from(new Set(flatUnsupportedFields));
    if (uniqueUnsupportedFields.length > 0) {
      this.unsupportedFieldsEl.innerText = 'Unsupported fields: ' +
        uniqueUnsupportedFields.join(', ');
    }

    const searchLimitReached = chartData.some((d) => d.searchLimitReached);
    if (searchLimitReached) {
      this.searchLimitEl.style.display = 'block';
    }
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
      const callPromise = this.prpcClient.call('monorail.Issues',
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

  _chartConfig(indices, values) {
    return {
      type: 'line',
      data: {
        labels: indices,
        datasets: [{
          label: 'Issue count',
          backgroundColor: 'rgb(54, 162, 235)',
          borderColor: 'rgb(54, 162, 235)',
          data: values,
          fill: false,
        }]
      },
      options: {
        responsive: true,
        title: {
          display: true,
          text: 'Issues over time'
        },
        tooltips: {
          mode: 'index',
          intersect: false,
        },
        hover: {
          mode: 'nearest',
          intersect: true
        },
        scales: {
          xAxes: [{
            display: true,
            scaleLabel: {
              display: true,
              labelString: 'Day'
            }
          }],
          yAxes: [{
            display: true,
            ticks: {
              beginAtZero: true,
            },
            scaleLabel: {
              display: true,
              labelString: 'Value'
            }
          }]
        }
      }
    };
  }

  _template() {
    const tmpl = document.createElement('template');
    // Warning: do not interpolate any variables into the below string.
    // Also don't use innerHTML anywhere other than in this specific scenario.
    tmpl.innerHTML = `
      <style>
        div#container {
          max-width: 800px;
          margin: 0 auto;
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
        }
        ::-webkit-progress-bar {
          background-color: white;
        }
        progress::-webkit-progress-value {
          transition: width 1s;
          background-color: rgb(54, 162, 235);
        }
      </style>
      <div id="container">
        <canvas id="canvas"></canvas>
        <div id="options">
          <p id="unsupported-fields"></p>
          <progress value="0.05" style="width: 100%; visibility: visible;">Loading chart...</progress>
          <p id="search-limit-message">
            Note: Some results are not being counted.
            Please narrow your query.
          </p>
          <label for="end-date">Choose end date:</label>
          <br />
          <input type="date" id="end-date" name="end-date" value="" />
        </div>
      </div>
    `;
    return tmpl;
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
    const dateFormat = { year: 'numeric', month: 'numeric', day: 'numeric' };
    return timestamps.map(ts => (
      (new Date(ts * 1000)).toLocaleDateString('en-US', dateFormat)
    ));
  }

}

customElements.define(MrChart.is(), MrChart);
