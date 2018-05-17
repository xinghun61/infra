'use strict';

/**
 * `<mr-approval-page>`
 *
 * The main entry point for a given launch issue.
 *
 */
class MrApprovalPage extends Polymer.Element {
  static get is() {
    return 'mr-approval-page';
  }

  static get properties() {
    return {
      issueId: {
        type: Number,
        computed: '_computeIssueId(queryParams.id)',
      },
      gates: Array,
      queryParams: Object,
      user: {
        type: String,
        computed: '_computeUser(queryParams.you)',
      },
    };
  }

  _computeIssueId(id) {
    return id * 1;
  }

  // TODO(zhangtiff): Remove the "you" feature once we have real authentication.
  _computeUser(you) {
    if (!you) return;
    return `${you}@chromium.org`;
  }
}

customElements.define(MrApprovalPage.is, MrApprovalPage);
