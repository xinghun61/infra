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
      _onSubmitComment: {
        type: Function,
        value: function() {
          return this._submitCommentHandler.bind(this);
        },
      },
      _updateDescription: {
        type: Function,
        value: function() {
          return this._updateDescriptionHandler.bind(this);
        },
      },
    };
  }

  _submitCommentHandler(comment, files) {
    this._updateIssue(comment, files);
  }

  _updateDescriptionHandler(content) {
    this._updateIssue(content, null, null, true);
  }

  _loadLocalFile(f) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onloadend = () => {
        resolve({filename: f.name, content: btoa(r.result)});
      };
      r.onerror = () => {
        reject(r.error);
      };

      r.readAsBinaryString(f);
    });
  }

  _updateIssue(commentData, files, delta, isDescription) {
    files = files || [];
    // Read file contents from local disk into binary strings, which
    // we can pass to UpdateIssue as an AttachmentUpload message.
    const loads = files.map((f) => {
      return this._loadLocalFile(f);
    });

    Promise.all(loads).then((uploads) => {
      const message = {
        trace: {token: this.token},
        issueRef: {
          projectName: this.projectName,
          localId: this.issueId,
        },
        commentContent: commentData || '',
      };

      if (uploads && uploads.length) {
        message.uploads = uploads;
      }

      if (delta) {
        message.delta = delta;
      }

      if (isDescription) {
        message.isDescription = true;
      }
      // TODO(seanmccullough): add state changes for updatingIssue so
      // this can disable/re-enable fields while upload is in progress.
      actionCreator.updateIssue(this.dispatch.bind(this), message);
    }).catch((reason) => {
      console.error('loading file for attachment: ', reason);
    });
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
