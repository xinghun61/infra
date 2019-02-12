// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {dom} from '@polymer/polymer/lib/legacy/polymer.dom.js';

import '../../chops/chops-dialog/chops-dialog.js';
import '../../chops/chops-timestamp/chops-timestamp.js';
import '../../mr-bug-link/mr-bug-link.js';
import '../../mr-user-link/mr-user-link.js';
import {actionCreator} from '../../redux/redux-mixin.js';
import {selectors} from '../../redux/selectors.js';
import {MetadataMixin} from '../shared/metadata-mixin.js';
import '../shared/mr-flt-styles.js';
import './mr-field-values.js';
import './mr-issue-table.js';
import './mr-update-issue-hotlists.js';

/**
 * `<mr-metadata>`
 *
 * Generalized metadata for either approvals or issues.
 *
 */
export class MrMetadata extends MetadataMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <style include="mr-flt-styles">
        :host {
          display: table;
          table-layout: fixed;
          width: 100%;
        }
        td, th {
          padding: 0.5em 4px;
          vertical-align: top;
          text-overflow: ellipsis;
          overflow: hidden;
        }
        td {
          width: 60%;
        }
        th {
          text-align: left;
          width: 40%;
        }
        .group-separator {
          border-top: var(--chops-normal-border);
        }
        .group-title {
          font-weight: normal;
          font-style: oblique;
          border-bottom: var(--chops-normal-border);
          text-align: center;
        }
      </style>
      <template is="dom-if" if="[[approvalStatus]]">
        <tr>
          <th>Status:</th>
          <td>
            [[approvalStatus]]
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[approvers.length]]">
        <tr>
          <th>Approvers:</th>
          <td>
            <template is="dom-repeat" items="[[approvers]]">
              <mr-user-link
                display-name="[[item.displayName]]"
                user-id="[[item.userId]]"
              ></mr-user-link><br />
            </template>
          </td>
        </tr>
      </template>
      <template is="dom-if" if="[[setter]]">
        <th>Setter:</th>
        <td>
          <mr-user-link
            display-name="[[setter.displayName]]"
            user-id="[[setter.userId]]"
          ></mr-user-link>
        </td>
      </template>

      <template is="dom-if" if="[[owner]]">
        <tr>
          <th>Owner:</th>
          <td>
            <mr-user-link
              display-name="[[owner.displayName]]"
              user-id="[[owner.userId]]"
            ></mr-user-link>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[cc.length]]">
        <tr>
          <th>CC:</th>
          <td>
            <template is="dom-repeat" items="[[cc]]">
              <mr-user-link
                display-name="[[item.displayName]]"
                user-id="[[item.userId]]"
              ></mr-user-link><br />
            </template>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[issueStatus]]">
        <tr>
          <th>Status:</th>
          <td>
            [[issueStatus.status]]
            <em hidden$="[[!issueStatus.meansOpen]]">
              (Open)
            </em>
            <em hidden$="[[issueStatus.meansOpen]]">
              (Closed)
            </em>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[_issueIsDuplicate(issueStatus)]]">
        <tr>
          <th>MergedInto:</th>
          <td>
            <mr-bug-link
              project-name="[[projectName]]"
              issue="[[_getIssueForRef(blockerReferences, mergedInto)]]"
              is-closed$="[[_getIsClosedForRef(blockerReferences, mergedInto)]]"
            ></mr-bug-link>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[components.length]]">
        <tr>
          <th>Components:</th>
          <td>
            <template is="dom-repeat" items="[[components]]">
              <a href$="/p/[[projectName]]/issues/list?q=component:[[item.path]]"
                title$="[[item.path]] = [[item.docstring]]"
              >
                [[item.path]]
              </a>
            </template>
          </td>
        </tr>
      </template>

      <template is="dom-repeat" items="[[_fieldDefsWithGroups]]" as="group">
        <tr>
          <th class="group-title" colspan="2">
            [[group.groupName]]
          </th>
        </tr>
        <template is="dom-repeat" items="[[group.fieldDefs]]" as="field">
          <tr hidden$="[[_fieldIsHidden(fieldValueMap, field)]]">
            <th title$="[[field.fieldRef.fieldName]]">[[field.fieldRef.fieldName]]:</th>
            <td>
              <mr-field-values
                name="[[field.fieldRef.fieldName]]"
                type="[[field.fieldRef.type]]"
                values="[[_valuesForField(fieldValueMap, field.fieldRef.fieldName, phaseName)]]"
                project-name="[[projectName]]"
              ></mr-field-values>
            </td>
          </tr>
        </template>
        <tr>
          <th class="group-separator" colspan="2"></th>
        </tr>
      </template>

      <template is="dom-repeat" items="[[_fieldDefsWithoutGroup]]" as="field">
        <tr hidden$="[[_fieldIsHidden(fieldValueMap, field)]]">
          <th title$="[[field.fieldRef.fieldName]]">[[field.fieldRef.fieldName]]:</th>
          <td>
            <mr-field-values
              name="[[field.fieldRef.fieldName]]"
              type="[[field.fieldRef.type]]"
              values="[[_valuesForField(fieldValueMap, field.fieldRef.fieldName)]]"
              project-name="[[projectName]]"
            ></mr-field-values>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[sortedBlockedOn.length]]">
        <tr>
          <th>BlockedOn:</th>
          <td>
            <template is="dom-repeat" items="[[sortedBlockedOn]]">
              <mr-bug-link
                project-name="[[projectName]]"
                issue="[[_getIssueForRef(blockerReferences, item)]]"
                is-closed$="[[_getIsClosedForRef(blockerReferences, item)]]"
              >
              </mr-bug-link>
              <br />
            </template>
            <chops-button
              on-click="openViewBlockedOn">
              <i class="material-icons">view_list</i>
              &nbsp;View details
            </chops-button>
          </td>
        </tr>
        <chops-dialog id="viewBlockedOnDialog">
          <mr-issue-table
            id="viewBlockedOnTable"
            columns="[[blockedOnTableColumns]]"
            rows="[[blockedOnTableRows]]"
            on-reorder="reorderBlockedOn"
            rerank-enabled="[[blockedOnIssuesRerankEnabled]]"
          >
          </mr-issue-table>
        </chops-dialog>
      </template>

      <template is="dom-if" if="[[blocking]]">
        <tr>
          <th>Blocking:</th>
          <td>
            <template is="dom-repeat" items="[[blocking]]">
              <mr-bug-link
                project-name="[[projectName]]"
                issue="[[_getIssueForRef(blockerReferences, item)]]"
                is-closed$="[[_getIsClosedForRef(blockerReferences, item)]]"
              >
              </mr-bug-link>
              <br />
            </template>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[modifiedTimestamp]]">
        <tr>
          <th>Modified:</th>
          <td>
            <chops-timestamp timestamp="[[modifiedTimestamp]]" short></chops-timestamp>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[showUserHotlists]]">
        <tr>
          <th>
            Your Hotlists:
          </th>
          <td>
            <template is="dom-if" if="[[hotlistsByRole.user.length]]">
              <template is="dom-repeat" items="[[hotlistsByRole.user]]">
                <a href$="/u/[[item.ownerRef.userId]]/hotlists/[[item.name]]"
                  title$="[[item.name]] - [[item.summary]]">
                  [[item.name]]
                </a>
                <br />
              </template>
            </template>
            <chops-button
              on-click="openUpdateHotlists">
              <i class="material-icons">create</i>
              Update your hotlists
            </chops-button>
          </td>
        </tr>
      </template>
      <chops-dialog id="updateHotlistsDialog">
        <mr-update-issue-hotlists
          id="updateHotlistsForm"
          on-discard="closeUpdateHotlists"
          on-save="saveUpdateHotlists"
        >
        </mr-update-issue-hotlists>
      </chops-dialog>

      <template is="dom-if" if="[[hotlistsByRole.participants.length]]">
        <tr>
          <th>Participant's Hotlists:</th>
          <td>
            <template is="dom-repeat" items="[[hotlistsByRole.participants]]">
              <a href$="/u/[[item.ownerRef.userId]]/hotlists/[[item.name]]"
                title$="[[item.name]] - [[item.summary]]">
                [[item.name]]
              </a>
              <br />
            </template>
          </td>
        </tr>
      </template>

      <template is="dom-if" if="[[hotlistsByRole.others.length]]">
        <tr>
          <th>Other Hotlists:</th>
          <td>
            <template is="dom-repeat" items="[[hotlistsByRole.others]]">
              <a href$="/u/[[item.ownerRef.userId]]/hotlists/[[item.name]]"
                title$="[[item.name]] - [[item.summary]]">
                [[item.name]]
              </a>
              <br />
            </template>
          </td>
        </tr>
      </template>
    `;
  }

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
      mergedInto: Object,
      owner: Object,
      isApproval: {
        type: Boolean,
        value: false,
      },
      projectName: String,
      issueId: Number,
      user: Object,
      issuePermissions: Object,
      blockerReferences: Object,
      role: {
        type: String,
        value: 'table',
        reflectToAttribute: true,
      },
      issueHotlists: Array,
      hotlistsByRole: {
        type: Object,
        computed: '_splitIssueHotlistsByRole(issueHotlists, user, owner, cc)',
      },
      sortedBlockedOn: {
        type: Array,
        computed: '_sortBlockedOn(blockerReferences, blockedOn)',
      },
      blockedOnTableColumns: {
        type: Array,
        value: ['Issue', 'Summary'],
      },
      blockedOnTableRows: {
        type: Array,
        computed: '_blockedOnTableRows(blockerReferences, sortedBlockedOn)',
      },
      blockedOnIssuesRerankEnabled: {
        type: Boolean,
        computed: '_canRerankBlockedOnIssues(issuePermissions)',
      },
      showUserHotlists: {
        type: Boolean,
        computed: '_computeShowUserHotlists(user, isApproval)',
      },
      fieldValueMap: Object,
    };
  }

  static mapStateToProps(state, element) {
    return {
      projectName: state.projectName,
      issueId: state.issueId,
      user: state.user,
      issuePermissions: state.issuePermissions,
      blockerReferences: state.blockerReferences,
      issueHotlists: state.issueHotlists,
      fieldValueMap: selectors.issueFieldValueMap(state),
    };
  }

  _computeShowUserHotlists(user, isApproval) {
    return user && !isApproval;
  }

  _blockedOnTableRows(blockerReferences, blockedOn) {
    return (blockedOn || []).map((blockerRef) => {
      const issue = this._getIssueForRef(blockerReferences, blockerRef);
      const isClosed = this._getIsClosedForRef(blockerReferences, blockerRef);
      const row = {
        draggable: !isClosed,
        cells: [
          {
            type: 'issue',
            projectName: this.projectName,
            issue: this._getIssueForRef(blockerReferences, blockerRef),
            isClosed: Boolean(isClosed),
          },
          {
            type: 'text',
            content: issue.summary,
          },
        ],
      };
      return row;
    });
  }

  _sortBlockedOn(blockerReferences, blockedOn) {
    const open = [];
    const closed = [];
    (blockedOn || []).forEach((ref) => {
      if (this._getIsClosedForRef(blockerReferences, ref)) {
        closed.push(ref);
      } else {
        open.push(ref);
      }
    });
    return open.concat(closed);
  }

  _canRerankBlockedOnIssues(issuePermissions) {
    return (issuePermissions || []).includes('editissue');
  }

  _makeIssueStrKey(issueRef) {
    if (!issueRef) return '';
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

  _issueIsDuplicate(issueStatus) {
    return issueStatus.status === 'Duplicate';
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
      promises.push(window.prpcClient.call(
        'monorail.Features', 'AddIssuesToHotlists', {
          hotlistRefs: changes.added,
          issueRefs: [issueRef],
        }
      ));
    }
    if (changes.removed.length) {
      promises.push(window.prpcClient.call(
        'monorail.Features', 'RemoveIssuesFromHotlists', {
          hotlistRefs: changes.removed,
          issueRefs: [issueRef],
        }
      ));
    }
    if (changes.created) {
      promises.push(window.prpcClient.call(
        'monorail.Features', 'CreateHotlist', {
          name: changes.created.name,
          summary: changes.created.summary,
          issueRefs: [issueRef],
        }
      ));
    }

    Promise.all(promises).then((results) => {
      actionCreator.fetchIssueHotlists(this.dispatchAction.bind(this), issueRef);
      actionCreator.fetchUserHotlists(
        this.dispatchAction.bind(this), this.user.email);
      this.$.updateHotlistsDialog.close();
    }, (error) => {
      this.$.updateHotlistsForm.error = error.description;
    });
  }

  openViewBlockedOn() {
    dom(this.root).querySelector('#viewBlockedOnTable').reset();
    dom(this.root).querySelector('#viewBlockedOnDialog').open();
  }

  reorderBlockedOn(e) {
    const src = e.detail.src.cells[0].issue;
    const target = e.detail.target.cells[0].issue;

    const reorderRequest = window.prpcClient.call(
      'monorail.Issues', 'RerankBlockedOnIssues', {
        issueRef: {
          projectName: this.projectName,
          localId: this.issueId,
        },
        movedRef: {
          projectName: src.projectName,
          localId: src.localId,
        },
        targetRef: {
          projectName: target.projectName,
          localId: target.localId,
        },
        splitAbove: e.detail.above,
      });

    reorderRequest.then((response) => {
      actionCreator.fetchIssue(this.dispatchAction.bind(this), {
        issueRef: {
          projectName: this.projectName,
          localId: this.issueId,
        },
      });
    }, (error) => {
      this.$.viewBlockedOnTable.reset();
      this.$.viewBlockedOnTable.error = error.description;
    });
  }
}

customElements.define(MrMetadata.is, MrMetadata);
