/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

import '../../../node_modules/@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {ReduxMixin} from '../../redux/redux-mixin.js';
import './mr-phase.js';

/**
 * `<mr-launch-overview>`
 *
 * This is a shorthand view of the phases for a user to see a quick overview.
 *
 */
export class MrLaunchOverview extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style>
        :host {
          width: 100%;
          display: flex;
          flex-flow: column;
          justify-content: flex-start;
          align-items: stretch;
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
      approvals: Array,
      phases: Array,
      _phaselessApprovals: {
        type: Array,
        computed: '_approvalsForPhase(approvals)',
      },
    };
  }

  static mapStateToProps(state, element) {
    if (!state.issue) return;
    return {
      approvals: state.issue.approvalValues,
      phases: state.issue.phases,
    };
  }

  _approvalsForPhase(approvals, phaseName) {
    return approvals.filter((a) => {
      // We can assume phase names will be unique.
      return a.phaseRef.phaseName == phaseName;
    });
  }
}
customElements.define(MrLaunchOverview.is, MrLaunchOverview);
