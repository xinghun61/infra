// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '/deployed_node_modules/chart.js/dist/Chart.min.js';

const DEFAULT_NUM_DAYS = 14;

class MrChart extends HTMLElement {

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

    this.timestamps = this._makeTimestamps(DEFAULT_NUM_DAYS);
    const indices = this._makeIndices(this.timestamps);

    this.values = [];

    // Attach DOM and initialize chart onto canvas.
    const shadowRoot = this.attachShadow({mode: 'open'});
    shadowRoot.appendChild(this._makeTemplate().content.cloneNode(true));
    const ctx = shadowRoot.getElementById('canvas').getContext('2d');
    this.chart = new window.Chart(ctx, this._chartConfig(indices, this.values));

    this._fetchData(this.timestamps);
  }

  // Populate array of timestamps we want to fetch.
  _makeTimestamps(numDaysBack) {
    const endTimeSeconds = this._getEndTime();
    const secondsInDay = 24 * 60 * 60;
    const timestamps = [];
    for (let i = 0; i < numDaysBack; i++) {
      timestamps.unshift(endTimeSeconds - (secondsInDay * i));
    }
    return timestamps;
  }

  // Get the chart end time from either the URL or current time.
  _getEndTime() {
    const urlParams = new URLSearchParams(window.location.search);
    const endDateString = urlParams.get('end_date');
    let year, month, day;
    if (endDateString) {
      const splitEndDate = endDateString.split('-');
      year = Number(splitEndDate[0]);
      month = Number(splitEndDate[1]) - 1;
      day = Number(splitEndDate[2]);
    } else {
      const today = new Date();
      year = today.getUTCFullYear();
      month = today.getUTCMonth();
      day = today.getUTCDate();
    }

    // Align the date to EOD UTC.
    const timestampMs = Date.UTC(year, month, day, 23, 59, 59);
    // Return seconds since back-end expects seconds.
    return Math.round(timestampMs / 1000);
  }

  _makeIndices(timestamps) {
    const dateFormat = { year: 'numeric', month: 'numeric', day: 'numeric' };
    return timestamps.map(ts => (
      (new Date(ts * 1000)).toLocaleDateString('en-US', dateFormat)
    ));
  }

  _updateChartValues() {
    if (this._animationFrameRequested) {
      return;
    }

    this._animationFrameRequested = true;
    window.requestAnimationFrame(() => {
      this.chart.data.datasets[0].data = this.values;
      this.chart.update();
      this._animationFrameRequested = false;
    });
  }

  async _fetchData(timestamps) {
    // TODO(jeffcarp, 4387): Load data points in bisect order.
    const fetchPromises = timestamps.map(async (ts, index) => {
      const data = await this._fetchDataAtTimestamp(ts);
      this.values[index] = data.issues;
      this._updateChartValues();
      return data;
    });

    Promise.all(fetchPromises).then((chartData) => {
      // TODO(jeffcarp): Reintroduce unsupported fields into UI.
      const flatUnsupportedFields = chartData.reduce((acc, datum) => {
        acc = acc.concat(datum.unsupportedField);
        return acc;
      }, []);
      this.unsupportedFields = Array.from(new Set(flatUnsupportedFields));
    });
  }

  _fetchDataAtTimestamp(timestamp) {
    return new Promise((resolve, reject) => {
      const params = new URLSearchParams(document.location.search.substring(1));
      const query = params.get('q');
      const message = {
        timestamp: timestamp,
        projectName: this.projectName,
        query: query,
      };
      const callPromise = window.prpcClient.call('monorail.Issues',
          'IssueSnapshot', message);
      return callPromise.then(response => {
        resolve({
          date: timestamp * 1000,
          issues: response.snapshotCount[0].count,
          unsupportedField: response.unsupportedField,
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

  _makeTemplate() {
    const templateEl = document.createElement('template');
    const div = document.createElement('div');
    div.style.maxWidth = '800px';
    div.style.margin = '0 auto';

    const canvas = document.createElement('canvas');
    canvas.id = 'canvas';

    // TODO(jeffcarp, 4384): Add progress bar.

    div.appendChild(canvas);
    templateEl.content.appendChild(div);

    return templateEl;
  }

}

customElements.define(MrChart.is(), MrChart);

