'use strict';

/**
 * `<mr-issue-details>`
 *
 * This is the main details section for a given issue.
 *
 */
class MrIssueDetails extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-issue-details';
  }

  // TODO(zhangtiff): Replace this with real data.
  static get properties() {
    return {
      comments: {
        type: Array,
        statePath: 'comments',
      },
      _description: {
        type: String,
        computed: '_computeDescription(comments)',
      },
      _comments: {
        type: Array,
        computed: '_filterComments(comments)',
      },
    };
  }

  _filterComments(comments) {
    return comments.filter((c) => (!c.descriptionNum && !c.approvalRef));
  }

  _computeDescription(comments) {
    return comments.find((c) => (c.descriptionNum === 1));
  }
}
customElements.define(MrIssueDetails.is, MrIssueDetails);
