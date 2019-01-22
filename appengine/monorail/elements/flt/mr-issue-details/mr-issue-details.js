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

  static get properties() {
    return {
      comments: {
        type: Array,
        statePath: 'comments',
      },
      issueId: {
        type: Number,
        statePath: 'issueId',
      },
      projectName: {
        type: String,
        statePath: 'projectName',
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

  _updateDescriptionHandler(evt) {
    if (!evt || !evt.detail) return;
    const message = {
      trace: {token: this.token},
      issueRef: {
        projectName: this.projectName,
        localId: this.issueId,
      },
      commentContent: evt.detail.commentContent,
      isDescription: true,
      sendEmail: evt.detail.sendEmail,
    };

    actionCreator.updateIssue(this.dispatch.bind(this), message);
  }

  _filterComments(comments) {
    return comments.filter((c) => (!c.approvalRef && c.sequenceNum));
  }

  _computeDescription(comments) {
    for (let i = comments.length - 1; i >= 0; i--) {
      if (!comments[i].approvalRef && comments[i].descriptionNum) {
        return comments[i];
      }
    }
    return {};
  }
}
customElements.define(MrIssueDetails.is, MrIssueDetails);
