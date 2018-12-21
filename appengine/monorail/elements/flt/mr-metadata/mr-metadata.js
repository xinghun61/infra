'use strict';

/**
 * `<mr-metadata>`
 *
 * Generalized metadata for either approvals or issues.
 *
 */
class MrMetadata extends MetadataMixin(Polymer.Element) {
  static get is() {
    return 'mr-metadata';
  }

  static get properties() {
    return {
      approvalStatus: String,
      approvers: Array,
      setter: Object,
      cc: Array,
      components: Array,
      issueStatus: String,
      blockedOn: Array,
      blocking: Array,
      owner: Object,
      phaseName: String,
      projectName: {
        type: String,
        statePath: 'projectName',
      },
      issueId: {
        type: Number,
        statePath: 'issueId',
      },
      user: {
        type: Object,
        statePath: 'user',
      },
      blockerReferences: {
        type: Object,
        statePath: 'blockerReferences',
      },
      role: {
        type: String,
        value: 'table',
        reflectToAttribute: true,
        readOnly: true,
      },
      issueHotlists: {
        type: Array,
        statePath: 'issueHotlists',
      },
      hotlistsByRole: {
        type: Object,
        computed: '_splitIssueHotlistsByRole(issueHotlists, user, owner, cc)',
      },
    };
  }

  _makeIssueStrKey(issueRef) {
    return `${issueRef.projectName}:${issueRef.localId}`;
  }

  _getIssueForRef(blockerReferences, issueRef) {
    const key = this._makeIssueStrKey(issueRef);
    if (!blockerReferences || !blockerReferences.has(key)) return issueRef;
    return blockerReferences.get(key).issue;
  }

  _getIsClosedForRef(blockerReferences, issueRef) {
    const key = this._makeIssueStrKey(issueRef);
    if (!blockerReferences || !blockerReferences.has(key)) return false;
    return blockerReferences.get(key).isClosed;
  }

  _fieldIsHidden(fieldValueMap, fieldDef) {
    return fieldDef.isNiche && !this._valuesForField(fieldValueMap,
      fieldDef.fieldRef.fieldName).length;
  }

  _userIsParticipant(user, owner, cc) {
    if (owner && owner.userId === user.userId) {
      return true;
    }
    return cc && cc.some((ccUser) => ccUser && ccUser.UserId === user.userId);
  }

  _splitIssueHotlistsByRole(issueHotlists, user, owner, cc) {
    const hotlists = {
      user: [],
      participants: [],
      others: [],
    };
    (issueHotlists || []).forEach((hotlist) => {
      if (user && hotlist.ownerRef.userId === user.userId) {
        hotlists.user.push(hotlist);
      } else if (this._userIsParticipant(hotlist.ownerRef, owner, cc)) {
        hotlists.participants.push(hotlist);
      } else {
        hotlists.others.push(hotlist);
      }
    });
    return hotlists;
  }

  openUpdateHotlists() {
    this.$.updateHotlistsForm.reset();
    this.$.updateHotlistsDialog.open();
  }

  closeUpdateHotlists() {
    this.$.updateHotlistsDialog.close();
  }

  saveUpdateHotlists() {
    const changes = this.$.updateHotlistsForm.changes;
    const issueRef = {
      projectName: this.projectName,
      localId: this.issueId,
    };

    const promises = [];
    if (changes.added.length) {
      promises.push(window.prpcCall(
        'monorail.Features', 'AddIssuesToHotlists', {
          hotlistRefs: changes.added,
          issueRefs: [issueRef],
        }
      ));
    }
    if (changes.removed.length) {
      promises.push(window.prpcCall(
        'monorail.Features', 'RemoveIssuesFromHotlists', {
          hotlistRefs: changes.removed,
          issueRefs: [issueRef],
        }
      ));
    }
    if (changes.created) {
      promises.push(window.prpcCall(
        'monorail.Features', 'CreateHotlist', {
          name: changes.created.name,
          summary: changes.created.summary,
          issueRefs: [issueRef],
        }
      ));
    }

    Promise.all(promises).then((results) => {
      actionCreator.fetchIssueHotlists(this.dispatch.bind(this), issueRef);
      actionCreator.fetchUserHotlists(
        this.dispatch.bind(this), this.user.email);
      this.$.updateHotlistsDialog.close();
    }, (error) => {
      this.$.updateHotlistsForm.error = error.description;
    });
  }
}

customElements.define(MrMetadata.is, MrMetadata);
