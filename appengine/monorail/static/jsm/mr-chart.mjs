// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '/deployed_node_modules/chart.js/dist/Chart.min.js';


class MrChart extends HTMLElement {

  static is() {
    return 'mr-chart';
  }

  constructor() {
    super();

    this.projectName = this.getAttribute('project-name');
    if (!this.projectName || !this.projectName.length) {
      throw new Error('Attribute `project-name` required.');
    }
  }

  async connectedCallback() {
    const shadowRoot = this.attachShadow({mode: 'open'});
    shadowRoot.appendChild(this._makeTemplate().content.cloneNode(true));

    await this._fetchData();

    const ctx = shadowRoot.getElementById('canvas').getContext('2d');
    this.chart = new window.Chart(ctx, this._chartConfig());
  }

  _fetchData() {
    // Populate array of timestamps we want to fetch.
    const currentUnixSeconds = Math.round((new Date()).getTime() / 1000);
    const secondsInDay = 24 * 60 * 60;
    const numDays = 14;
    const timestamps = [];
    for (let i = 0; i < numDays; i++) {
      timestamps.unshift(currentUnixSeconds - (secondsInDay * i));
    }

    const dateFormat = { year: 'numeric', month: 'numeric', day: 'numeric' };
    this.indices = timestamps.map(ts => (
      (new Date(ts * 1000)).toLocaleDateString('en-US', dateFormat)
    ));

    // TODO(jeffcarp, 4387): Don't load all data points at once, bisect.
    const fetchPromises = timestamps.map((ts) => this._fetchDataAtTimestamp(ts));
    return Promise.all(fetchPromises).then(chartData => {
      this.values = chartData.map((data) => data.issues);

      // Calculate unsupported fields.
      const flatUnsupportedFields = chartData.reduce((acc, datum) => {
        acc = acc.concat(datum.unsupportedField);
        return acc;
      }, []);
      // TODO(jeffcarp): Re-display unsupported fields
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

  _chartConfig() {
    return {
      type: 'line',
      data: {
        labels: this.indices,
        datasets: [{
          backgroundColor: 'rgb(54, 162, 235)',
          borderColor: 'rgb(54, 162, 235)',
          data: this.values,
          fill: false,
        }]
      },
      options: {
        responsive: true,
        title: {
          display: false,
          text: 'Issue count over time'
        },
        legend: {
          display: false,
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
              labelString: 'Issue Count'
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

    div.appendChild(canvas);
    templateEl.content.appendChild(div);

    return templateEl;
  }

}

customElements.define(MrChart.is(), MrChart);

