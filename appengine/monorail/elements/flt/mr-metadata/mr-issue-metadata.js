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
      projectConfig: {
        type: Object,
        statePath: 'projectConfig',
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
      token: {
        type: String,
        statePath: 'token',
      },
      _fieldDefs: {
        type: Array,
        computed: '_computeIssueFieldDefs(projectConfig.fieldDefs, _type)',
      },
      _canStar: {
        type: Boolean,
        computed: '_computeCanStar(fetchingIsStarred, starringIssue)',
      },
      _type: {
        type: String,
        computed: '_computeIssueType(issue.fieldValues)',
      },
    };
  }

  edit() {
    this.dispatch({
      type: actionType.OPEN_DIALOG,
      dialog: DialogState.EDIT_ISSUE,
    });
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

  _computeIssueType(fieldValues) {
    return computeFunction.computeIssueType(fieldValues);
  }

  _computeIssueFieldDefs(fields, applicableType) {
    return computeFunction.computeFieldDefs(fields, applicableType, null);
  }

  _renderPluralS(count) {
    return count == 1 ? '' : 's';
  }

  _renderCount(count) {
    return count ? count : 0;
  }
}

customElements.define(MrIssueMetadata.is, MrIssueMetadata);
