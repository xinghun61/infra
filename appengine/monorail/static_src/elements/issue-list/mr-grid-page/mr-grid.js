// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html} from 'lit-element';
import {extractGridData} from './extract-grid-data.js';

export class MrGrid extends LitElement {
  render() {
    return html`
      <p>xHeadings</p>
      ${this.xHeadings.map((heading) => html`
        <p>${heading}</p>`)}
      <p>yHeadings</p>
      ${this.yHeadings.map((heading) => html`
        <p>${heading}</p>`)}
    `;
  }

  static get properties() {
    return {
      xAttr: {type: String},
      yAttr: {type: String},
      xHeadings: {type: Array},
      yHeadings: {type: Array},
      issues: {type: Array},
      cellMode: {type: String},
    };
  }

  constructor() {
    super();
    this.xHeadings = [];
    this.yHeadings = [];
  }

  updated(changedProperties) {
    if (changedProperties.has('xAttr') || changedProperties.has('yAttr') ||
        changedProperties.has('issues')) {
      const gridData = extractGridData(this.issues, this.xAttr, this.yAttr);
      this.xHeadings = gridData.xHeadings;
      this.yHeadings = gridData.yHeadings;
    }
  }
};
customElements.define('mr-grid', MrGrid);
