// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import '@polymer/paper-tooltip/paper-tooltip.js';
import {html} from '@polymer/polymer/lib/utils/html-tag.js';
import {PolymerElement} from '@polymer/polymer/polymer-element.js';

export class CurrentIncidentIcon extends PolymerElement {
  static get template() {
    return html`
      <style>
        .circle-container {
        padding-left: 10px;
      }
      .clickable {
        cursor: pointer;
      }
      </style>
      <link rel="stylesheet" type="text/css" href="/static/icons.css">
      <span id="jsCurrentIncident" class="class-container">
        <i class$="circle [[_getColorClass(_icon)]]"></i>
      </span>
    `;
  }

  static get is() { return 'current-incident-icon'; }

  ready() {
    super.ready();
  }

  static get properties() {
    return {
      incidents: {
        type: Array,
        value: () => { return []; }
      },
      isGoogler: {
        type: Boolean,
        value: false,
      },
      _icon: {
        type: Object,
        value: () => { return {'severity': 'GREEN', 'incidentLink': ''}; },
        computed: '_computeIcon(incidents)',
      },
    }
  }

  static get observers() {
    return [
      '_configureAccess(isGoogler, _icon.incidentLink)',
    ]
  }

  _getColorClass(incident) {
    return incident['severity'].toLowerCase();
  }

  _configureAccess(isGoogler, link) {
    if (isGoogler && link) {
      this.$.jsCurrentIncident.addEventListener("click", () => { window.location = link; });
      this.$.jsCurrentIncident.classList.add('clickable');
    }
  }

  _computeIcon(incidents) {
    let currentIncident = {'severity': 'GREEN', 'incidentLink': ''};
    for (let incident of incidents) {
      if (incident['open']) {
        if (incident['severity'] == 'RED') {
          currentIncident = incident;
          break;
        }
        // The incident is open but severity is not RED, so it must be YELLOW.
        // Keep looping in case there is an incident with severity == RED.
        currentIncident = incident;
      }
    }
    return currentIncident;
  }
}
customElements.define(CurrentIncidentIcon.is, CurrentIncidentIcon);
