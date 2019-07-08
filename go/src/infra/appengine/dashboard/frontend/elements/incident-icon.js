// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {html} from '@polymer/polymer/lib/utils/html-tag.js';
import {PolymerElement} from '@polymer/polymer/polymer-element.js';

/**
 * `<incident-icon>`
 *
 * Icon representing a service outage or disruption.
 *
 */
export class IncidentIcon extends PolymerElement {
  static get template() {
    return html`
      <style>
        .hidden {
          display: none !important;
        }
        .incident {
          display: table;
          left: var(--incident-left);
          min-width: 10px;
          position: absolute;
          top: 19px;
          width: var(--incident-width);
          /* Show red alerts if red + yellow alerts were active simultaneously.*/
          z-index: var(--incident-z-index);
        }
        .googler-access {
          cursor: pointer;
        }
      </style>
      <link rel="stylesheet" type="text/css" href="/static/icons.css">
      <i id="jsIncident" class="incident">
        <i id="jsLeft" class$="left [[_computeColor(incident)]]"></i>
        <i id="jsRight" class$="right [[_computeColor(incident)]]"></i>
      </i>
    `;
  }

  static get is() { return 'incident-icon'; }

  static get properties() {
    return {
      incident: {
        type: Object,
        value: () => {
          return {startTime: 0, endTime: 0, severity: 'yellow'}; },
      },
      // Array of Date objects
      dates: {
        type: Array,
        value: [],
      },
      isGoogler: {
        type: Boolean,
        value: false,
        observer: '_configureAccess',
      },
    }
  }

  static get observers() {
    return [
      '_computeStyle(incident, dates)'
    ]
  }

  _configureAccess() {
    if (this.isGoogler) {
      this.$.jsIncident.addEventListener("click", () => {
        window.location = this.incident.incidentLink;
      });
      this.$.jsIncident.classList.add('googler-access');
    }
  }

  _computeColor(incident) {
    return incident.severity.toLowerCase();
  }

  /**
   * This calculates the width and left start position (percentages)
   * that the icon should have based on the start/end_time of the
   * incident and which time period the dashboard is currently displaying.
   * If the incident started before or ended after the visible time span,
   * the left/right end icons should not be shown and the icon should
   * instead start/end with the middle icon, to represent the incident
   * going onto the next week.
   * @param {Object} incident - Object containing incident's data.
   * @param {Date[]} dates - The list of dates shown on the dashboard.
   */
  _computeStyle(incident, dates) {
    let startPosition = this.getDatePosition(incident.startTime, dates);
    if (startPosition === undefined) {
      // start_time is before first date on the dashboard.
      startPosition = 0;
      this.$.jsLeft.classList.add('hidden');
    }
    else {
      this.$.jsLeft.classList.remove('hidden');
    }

    let endPosition = this.getDatePosition(incident.endTime, dates);
    if (endPosition === undefined) {
      // end_time is after last date on the dashboard.
      endPosition = 100;
      this.$.jsRight.classList.add('hidden');
    }
    else {
      this.$.jsRight.classList.remove('hidden');
    }
    this.updateStyles({
      '--incident-left': `${startPosition}%`,
      '--incident-width': `${endPosition - startPosition}%`,
      '--incident-z-index':
      `${this._computeColor(incident) == 'red' ? 2 : 1}`,
    });
  }

  /**
   * getDatePosition returns a start position of an incident based on the
   * start_time unix and where that time falls within the given dates.
   * @param {string} incidentUnix - string Unix timestamp of start time.
   * @param {Date[]} dates - The list of dates being shown on the
   * dashboard.
   */
  getDatePosition(incidentUnix, dates) {
    const NUM_DAYS_DISPLAYED = 7;
    const TIME_INCREMENTS_PER_DAY = 168;
    let position;
    let incidentDate = new Date(parseInt(incidentUnix, 10) * 1000);
    let time = incidentDate.getHours();
    let zeroHourDate = incidentDate.setHours(0, 0, 0, 0);
    dates.forEach((date, i) => {
      if (date.setHours(0, 0, 0, 0) === zeroHourDate) {
        position = i / NUM_DAYS_DISPLAYED;
        position = (position + time / TIME_INCREMENTS_PER_DAY) * 100;
      }
    });
    return position;
  }
}
customElements.define(IncidentIcon.is, IncidentIcon);
