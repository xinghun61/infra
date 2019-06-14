// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

/**
 * `<chops-chart>`
 *
 * Web components wrapper around Chart.js.
 *
 */
export class ChopsChart extends LitElement {
  static get styles() {
    return css`
      :host {
        display: block;
      }
    `;
  }

  render() {
    return html`
      <canvas></canvas>
    `;
  }

  static get properties() {
    return {
      type: {type: String},
      data: {type: Object},
      options: {type: Object},
      _chart: {type: Object},
    };
  }

  constructor() {
    super();
    this.type = 'line';
    this.data = {};
    this.options = {};
  }

  async updated(changedProperties) {
    await import(/* webpackChunkName: "chartjs" */ 'chart.js/dist/Chart.bundle.min.js');
    if (!this._chart) {
      const {type, data, options} = this;
      const ctx = this.shadowRoot.querySelector('canvas').getContext('2d');
      this._chart = new window.Chart(ctx, {type, data, options});
    } else if (changedProperties.has('type') || changedProperties.has('data')
        || changedProperties.has('options')) {
      this._updateChart();
    }
  }

  _updateChart() {
    this._chart.type = this.type;
    this._chart.data = this.data;
    this._chart.options = this.options;

    this._chart.update();
  }
}

customElements.define('chops-chart', ChopsChart);
