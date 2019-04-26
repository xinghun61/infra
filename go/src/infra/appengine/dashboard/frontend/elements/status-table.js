// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {html} from '@polymer/polymer/lib/utils/html-tag.js';
import {PolymerElement} from '@polymer/polymer/polymer-element.js';

import 'current-incident-icon.js'
import 'service-row.js'
import 'table-footer.js'

const MARKER_POSITIONS = [
    `0`, `${100/7}`, `${200/7}`, `${300/7}`, `${400/7}`, `${500/7}`, `${600/7}`
  ];

/**
 * `<status-table>`
 *
 * The visual representation of services and their statuses and
 * past incidents.
 */
export class StatusTable extends PolymerElement {
  static get template() {
    return html`
      <style>
        * {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }
        .card {
          background-color: white;
          box-shadow: 0 4px 8px 0 rgba(0, 0, 0, 0.2), 0 6px 20px 0 rgba(0, 0, 0, 0.19);
          color: rgba(0, 0, 0, 0.87);
          font: 1.2em "Roboto";
          padding: 24px;
        }
        .date-th {
          width: 11.43%;
        }
        .footer,
        th {
          height: 56px;
        }
        .header {
          height: 64px;
          line-height: 64px; // vertically center text
        }
        .marker {
          background-color: #e8eaed;
          width: 2px;
          height: 26px;
          top: 12px;
          position: absolute;
        }
        table {
          border-collapse: collapse;
          font-family: 'Roboto', 'Noto', sans-serif;
          padding: 24px;
          width: 100%;
        }
        td {
          font-size: .81em;
          position: relative;
        }
        th {
          color: rgba(0, 0, 0, 0.54);
          font: .76em "Roboto";
        }
        th:first-child {
          text-align: left;
        }
        tr {
          border: solid silver;
          border-width: 1px 0;
          height: 48px;
        }
        tr:first-child {
          border-top: none;
        }
        tr:last-child {
          border-bottom: none;
        }
      </style>
      <div class="layout horizontal center-justified">
        <div class="card">
          <table>
            <tr>
              <th>Current Status</th>
              <template is="dom-repeat" items="[[formattedDates]]">
                <th class="date-th">[[item]]</th>
              </template>
            </tr>
            <template is="dom-repeat" items="[[services]]">
              <tr>
                <td>
                  <current-incident-icon incidents="[[item.incidents]]" is-googler="[[isGoogler]]"></current-incident-icon>
                  [[item.name]]
                </td>
                <td colspan="7">
                  <template is="dom-repeat" items="[[_markerPositions]]" as="position">
                    <i class="marker" style="left: [[position]]%"></i>
                  </template>
                  <service-row incidents="[[_computePreviousIncidents(item.incidents)]]"
                    dates="[[dates]]" is-googler="[[isGoogler]]"></service-row>
                </td>
              </tr>
            </template>
            <tr class="footer">
              <td colspan="8">
                <table-footer latest-date="{{latestDateTs}}"></table-footer>
              </dd>
            </tr>
          </table>
        </div>
      </div>
    `;
  }
  static get is() { return 'status-table'; }

  ready() {
    super.ready();
  }

  static get properties() {
    return {
      services: {
        type: Array,
        value: () => { return []; },
      },
      latestDateTs: {
        type: Number,
        notify: true,
      },
      // All dates shown on the dashboard should be the same across all
      // elements on the page.
      formattedDates: {
        type: Array,
        value: [],
      },
      dates: {
        type: Array,
        value: [],
      },
      _markerPositions: {
        type: Array,
        value: () => { return MARKER_POSITIONS; }
      },
      isGoogler: {
        type: Boolean,
        value: false,
      },
    }
  }

  static get observers() {
    return [
      '_updateDates(latestDateTs)',
    ]
  }

  _updateDates(latestDateTs) {
    const weekLooper = 6;
    let lastDate =
        latestDateTs ? new Date(latestDateTs) : new Date();
    this.splice('dates', 0, this.dates.length);
    this.splice('formattedDates', 0, this.formattedDates.length);
    for (let i = weekLooper; i >= 0; i--) {
      // date must be based on lastDate so setDate results in the
      // accurate month.
      let date = new Date(lastDate);
      date.setDate(lastDate.getDate() - i);
      this.push('dates', date);
      this.push('formattedDates',
		(`${date.getFullYear()}-${date.getMonth()+1}-${date.getDate()}`));
    }
  }

  _computePreviousIncidents(incidents) {
    let prevInc = [];
    incidents.forEach(incident => {
      if (!incident['open']) {
        prevInc.push(incident);
      }
    });
    return prevInc;
  }
}
customElements.define(StatusTable.is, StatusTable);
