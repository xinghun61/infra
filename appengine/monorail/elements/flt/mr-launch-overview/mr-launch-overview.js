'use strict';

/**
 * `<mr-launch-overview>`
 *
 * This is a shorthand view of the phases for a user to see a quick overview.
 *
 */
class MrLaunchOverview extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-launch-overview';
  }

  static get properties() {
    return {
      approvals: {
        type: Array,
        statePath: 'issue.approvalValues',
      },
      phases: {
        type: Array,
        statePath: 'issue.phases',
      },
      _phaselessApprovals: {
        type: Array,
        computed: '_approvalsForPhase(approvals)',
      },
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
