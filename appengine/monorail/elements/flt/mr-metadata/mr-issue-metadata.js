'use strict';

/**
 * `<mr-issue-metadata>`
 *
 * The metadata view for a single issue. Contains information such as the owner.
 *
 */
class MrIssueMetadata extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-issue-metadata';
  }

  static get properties() {
    return {
      issue: {
        type: Object,
        statePath: 'issue',
      },
      issueId: {
        type: Object,
        statePath: 'issueId',
      },
      projectName: {
        type: Object,
        statePath: 'projectName',
      },
      isStarred: {
        type: Boolean,
        value: false,
        statePath: 'isStarred',
      },
      fetchingIsStarred: {
        type: Boolean,
        statePath: 'fetchingIsStarred',
      },
      starringIssue: {
        type: Boolean,
        statePath: 'starringIssue',
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
      token: {
        type: String,
        statePath: 'token',
      },
      _fields: {
        type: Array,
        computed: '_filterFields(issue.fieldValues)',
      },
      _canStar: {
        type: Boolean,
        computed: '_computeCanStar(fetchingIsStarred, starringIssue)',
      },
    };
  }

  edit() {
    this.$.editMetadata.open();
  }

  cancel() {
    this.$.metadataForm.reset();
    this.$.editMetadata.close();
  }

  toggleStar() {
    if (!this._canStar) return;
    this.dispatch({type: actionType.STAR_ISSUE_START});

    const newIsStarred = !this.isStarred;
    const message = {
      trace: {token: this.token},
      issue_ref: {
        project_name: this.projectName,
        local_id: this.issueId,
      },
      starred: newIsStarred,
    };

    const starIssue = window.prpcClient.call(
      'monorail.Issues', 'StarIssue', message
    );

    starIssue.then((resp) => {
      this.dispatch({
        type: actionType.STAR_ISSUE_SUCCESS,
        starCount: resp.starCount,
        isStarred: newIsStarred,
      });
    }, (error) => {
      this.dispatch({
        type: actionType.STAR_ISSUE_FAILURE,
        error,
      });
    });
  }

  _computeCanStar(fetching, starring) {
    return !(fetching || starring);
  }

  _filterFields(fields) {
    if (!fields) return [];
    return fields.filter((f) => {
      return !f.fieldRef.approvalName;
    });
  }

  _renderPluralS(count) {
    return count == 1 ? '' : 's';
  }

  _renderCount(count) {
    return count ? count : 0;
  }
}

customElements.define(MrIssueMetadata.is, MrIssueMetadata);
