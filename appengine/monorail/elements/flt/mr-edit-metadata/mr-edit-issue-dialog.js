'use strict';

/**
 * `<mr-edit-issue-dialog>`
 *
 * Issue editing dialog.
 *
 */
class MrEditIssueDialog extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-edit-issue-dialog';
  }

  static get properties() {
    return {
      issue: {
        type: Object,
        statePath: 'issue',
      },
      issueId: {
        type: Number,
        statePath: 'issueId',
      },
      projectName: {
        type: Number,
        statePath: 'projectName',
      },
      openedDialog: {
        type: Number,
        statePath: 'openedDialog',
      },
      // TODO(zhangtiff): Get real data from jsonfeed API.
      statuses: {
        type: Array,
        statePath: 'projectConfig.statusDefs',
      },
      token: {
        type: String,
        statePath: 'token',
      },
      _labelNames: {
        type: Array,
        computed: '_computeLabelNames(issue.labelRefs)',
      },
      _fieldList: {
        type: Array,
        computed: '_computeFieldList(issue.fieldValues)',
      },
      _opened: {
        type: Boolean,
        computed: '_computeOpened(openedDialog)',
      },
      _openedChange: {
        type: Function,
        value: function() {
          return this._openedChangeHandler.bind(this);
        },
      },
    };
  }

  _computeLabelNames(labels) {
    if (!labels) return [];
    return labels.map((l) => l.label);
  }

  _computeFieldList(fields) {
    return computeFunction.computeFieldList(fields, null);
  }

  _computeOpened(openedDialog) {
    return openedDialog === DialogState.EDIT_ISSUE;
  }

  _openedChangeHandler(opened) {
    Polymer.dom(this.root).querySelector('#metadataForm').reset();
    // Opening the dialog happens outside the context of the dialog, through an
    // aciton dispatch.
    if (!opened) {
      this.dispatch({type: actionType.CLOSE_DIALOG});
    }
  }

  save() {
    const data = Polymer.dom(this.root).querySelector(
      '#metadataForm').getData();

    const message = {
      trace: {token: this.token},
      issue_ref: {
        project_name: this.projectName,
        local_id: this.issueId,
      },
    };

    const delta = {};

    if (data.comment) {
      message['comment_content'] = data.comment;
    }

    if (data.status !== this.issue.statusRef.status) {
      delta['status'] = data.status;
    }

    if (data.summary !== this.issue.summary) {
      delta['summary'] = data.summary;
    }

    const oldLabels = this._labelNames;
    const newLabels = data.labels;

    const equalsIgnoreCase = (a, b) => (a.toLowerCase() === b.toLowerCase());

    const labelsAdd = fltHelpers.arrayDifference(newLabels, oldLabels,
      equalsIgnoreCase);
    const labelsRemove = fltHelpers.arrayDifference(oldLabels,
      newLabels, equalsIgnoreCase);


    if (labelsAdd.length) {
      delta['label_refs_add'] = labelsAdd.map((label) => ({label}));
    }

    if (labelsRemove.length) {
      delta['label_refs_remove'] = labelsRemove.map((label) => ({label}));
    }

    if (Object.keys(delta).length > 0) {
      message.delta = delta;
    }

    if (message.comment_content || message.delta) {
      actionCreator.updateIssue(this.dispatch.bind(this), message);
    }

    this.cancel();
  }

  cancel() {
    this.$.editDialog.close();
  }
}

customElements.define(MrEditIssueDialog.is, MrEditIssueDialog);
