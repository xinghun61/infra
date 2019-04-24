// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import './mr-phase.js';

/**
 * `<mr-launch-overview>`
 *
 * This is a shorthand view of the phases for a user to see a quick overview.
 *
 */
export class MrLaunchOverview extends connectStore(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <style>
        :host {
          width: 100%;
          display: flex;
          flex-flow: column;
          justify-content: flex-start;
          align-items: stretch;
        }
        :host([hidden]) {
          display: none;
        }
        mr-phase {
          margin-bottom: 0.75em;
        }
      </style>
      <template is="dom-repeat" items="[[phases]]" as="phase">
        <mr-phase phase-name="[[phase.phaseRef.phaseName]]" approvals="[[_approvalsForPhase(approvals, phase.phaseRef.phaseName)]]"></mr-phase>
      </template>
      <template is="dom-if" if="[[_phaselessApprovals.length]]">
        <mr-phase approvals="[[_phaselessApprovals]]"></mr-phase>
      </template>
    `;
  }

  static get is() {
    return 'mr-launch-overview';
  }

  static get properties() {
    return {
      approvals: {
        type: Array,
        value: () => [],
      },
      phases: {
        type: Array,
        value: () => [],
      },
      hidden: {
        type: Boolean,
        reflectToAttribute: true,
        computed: '_computeIsHidden(phases, approvals)',
      },
      _phaselessApprovals: {
        type: Array,
        computed: '_approvalsForPhase(approvals)',
      },
    };
  }

  stateChanged(state) {
    if (!issue.issue(state)) return;
    this.setProperties({
      approvals: issue.issue(state).approvalValues,
      phases: issue.issue(state).phases,
    });
  }

  _computeIsHidden(phases, approvals) {
    return (!phases || !phases.length) && (!approvals || !approvals.length);
  }

  _approvalsForPhase(approvals, phaseName) {
    return (approvals || []).filter((a) => {
      // We can assume phase names will be unique.
      return a.phaseRef.phaseName == phaseName;
    });
  }
}
customElements.define(MrLaunchOverview.is, MrLaunchOverview);
