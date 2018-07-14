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
      openedDialog: {
        type: Number,
        statePath: 'openedDialog',
      },
      // TODO(zhangtiff): Get real data from jsonfeed API.
      statuses: {
        type: Array,
        value: [
          'Unconfirmed',
          'Untriaged',
          'Available',
          'Assigned',
          'Started',
        ],
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

  _computeOpened(openedDialog) {
    return openedDialog === DialogState.EDIT_ISSUE;
  }

  _openedChangeHandler(opened) {
    if (opened) {
      this.dispatch({
        type: actionType.OPEN_DIALOG,
        dialog: DialogState.EDIT_ISSUE,
      });
    } else {
      this.dispatch({type: actionType.CLOSE_DIALOG});
      this.$.metadataForm.reset();
    }
  }

  save() {
    this.$.editDialog.close();
  }

  cancel() {
    this.$.editDialog.close();
  }
}

customElements.define(MrEditIssueDialog.is, MrEditIssueDialog);
