'use strict';

/**
 * `<mr-bug-link>`
 *
 * Displays a link to a bug.
 *
 */
class MrBugLink extends Polymer.Element {
  static get is() {
    return 'mr-bug-link';
  }

  static get properties() {
    return {
      issue: Object,
      isClosed: {
        type: Boolean,
        reflectToAttribute: true,
      },
      projectName: String,
      issueUrl: {
        type: String,
        computed: '_computeIssueUrl(issue)',
      },
    };
  }

  _hideProjectName(mainProjectName, localProjectName) {
    if (!mainProjectName || !localProjectName) return true;
    return mainProjectName.toLowerCase() === localProjectName.toLowerCase();
  }

  _computeIssueUrl(issue) {
    const issueType = issue.approvalValues ? 'approval' : 'detail';
    return `/p/${issue.projectName}/issues/${issueType}?id=${issue.localId}`;
  }
}
customElements.define(MrBugLink.is, MrBugLink);
