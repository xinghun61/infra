// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import 'elements/issue-detail/metadata/mr-edit-field/mr-edit-field.js';
import 'elements/framework/mr-error/mr-error.js';


// TODO(jojwang): Move all useful FLT const to a shared file.
const TEXT_TO_STATUS_ENUM = {
  'NeedsReview': 'NEEDS_REVIEW',
  'NA': 'NA',
  'ReviewRequested': 'REVIEW_REQUESTED',
  'ReviewStarted': 'REVIEW_STARTED',
  'NeedInfo': 'NEED_INFO',
  'Approved': 'APPROVED',
  'NotApproved': 'NOT_APPROVED',
};

export const NO_UPDATES_MESSAGE =
  'User lacks approver perms for approval in all issues.';
export const NO_APPROVALS_MESSAGE = 'These issues don\'t have any approvals.';

export class MrBulkApprovalUpdate extends PolymerElement {
  static get template() {
    return html`
      <style>
        :host {
          display: block;
          margin-top: 30px;
          position: relative;
        }
        button.clickable-text {
          background: none;
          border: 0;
          color: hsl(0, 0%, 39%);
          cursor: pointer;
          text-decoration: underline;
        }
        .hidden {
          display: none; !important;
        }
        .message {
          background-color: beige;
          width: 500px;
        }
        .note {
          color: hsl(0, 0%, 25%);
          font-size: 0.85em;
          font-style: italic;
        }
        table {
          border: 1px dotted black;
          cellspacing: 0;
          cellpadding: 3;
        }
      </style>
      <button class="js-showApprovals clickable-text" on-click="fetchApprovals">Show Approvals</button>
      <template is="dom-if" if="[[approvals.length]]">
        <form>
          <table>
            <tbody><tr>
              <th><label for="approvalSelect">Approval:</label></th>
              <td>
                <select id="approvalSelect">
                  <template is="dom-repeat" items="[[approvals]]" as="approval">
                    <option value="[[approval.fieldRef.fieldName]]">[[  approval.fieldRef.fieldName  ]]</option>
                  </template>
                </select>
              </td>
            </tr>
            <tr>
              <th><label for="approversInput">Approvers:</label></th>
              <td>
                <mr-edit-field id="approversInput" type="USER_TYPE" multi=""></mr-edit-field>
              </td>
            </tr>
            <tr><th><label for="statusInput">Status:</label></th>
              <td>
                <select id="statusInput">
                  <option>---</option>
                  <template is="dom-repeat" items="[[statusOptions]]" as="status">
                    <option value="[[status]]">[[  status  ]]</option>
                  </template>
                </select>
              </td>
            </tr>
            <tr>
              <th><label for="commentText">Comment:</label></th>
              <td colspan="4"><textarea cols="30" rows="3" id="commentText" placeholder="Add an approval comment"></textarea></td>
            </tr>
            <tr>
              <td><button class="js-save" on-click="save">Update Approvals only</button></td>
              <td><span class="note">Note: Some approvals may not be updated if you lack approver perms.</span></td>
            </tr>
          </tbody></table>
        </form>
      </template>
      <div class="message">
        <template is="dom-if" if="[[responseMessage]]">[[responseMessage]]</template>
        <template is="dom-if" if="[[errorMessage]]">
          <mr-error>[[errorMessage]]</mr-error>
        </template>
      </div>
    `;
  }

  static get is() {
    return 'mr-bulk-approval-update';
  }

  static get properties() {
    return {
      approvals: {
        type: Array,
        value: () => [],
      },
      issueRefs: {
        type: Array,
        computed: '_computeIssueRefs(projectName, localIdsStr)',
      },
      localIdsStr: String,
      projectName: String,
      responseMessage: String,
      statusOptions: {
        type: Array,
        value: () => {
          return Object.keys(TEXT_TO_STATUS_ENUM);
        },
      },
    };
  }

  _computeIssueRefs(projectName, localIdsStr) {
    if (!projectName || !localIdsStr) return [];
    const issueRefs = [];
    const localIds = localIdsStr.split(',');
    localIds.forEach((localId) => {
      issueRefs.push({projectName: projectName, localId: localId});
    });
    return issueRefs;
  }

  fetchApprovals(evt) {
    const message = {issueRefs: this.issueRefs};
    window.prpcClient.call('monorail.Issues', 'ListApplicableFieldDefs', message).then(
      (resp) => {
        const root = this.shadowRoot;
        if (resp.fieldDefs) {
          this.approvals = resp.fieldDefs.filter((fieldDef) => {
            return fieldDef.fieldRef.type == 'APPROVAL_TYPE';
          });
        }
        if (!this.approvals.length) {
          this.errorMessage = NO_APPROVALS_MESSAGE;
        }
        root.querySelector('.js-showApprovals').classList.add('hidden');
      }, (error) => {
        root.querySelector('.js-showApprovals').classList.add('hidden');
        this.errorMessage = error;
      });
  }

  save(evt) {
    this.responseMessage = '';
    this.errorMessage = '';
    this.toggleDisableForm();
    const root = this.shadowRoot;
    const selectedFieldDef = this.approvals.find(
      (approval) => {
        return approval.fieldRef.fieldName == root.querySelector('#approvalSelect').value;
      }
    );
    const message = {
      issueRefs: this.issueRefs,
      fieldRef: selectedFieldDef.fieldRef,
      send_email: true,
    };
    const commentContent = root.querySelector('#commentText').value;
    if (commentContent) {
      message.commentContent = commentContent;
    }
    const delta = {};
    const statusInput = root.querySelector('#statusInput');
    if (statusInput.value != '---') {
      delta.status = TEXT_TO_STATUS_ENUM[statusInput.value];
    }
    const approversInput = root.querySelector('#approversInput');
    const approversAdded = approversInput.getValuesAdded();
    if (approversAdded.length) {
      delta.approverRefsAdd = approversAdded.map((name) => ({'displayName': name}));
    }
    if (Object.keys(delta).length) {
      message.approvalDelta = delta;
    }
    window.prpcClient.call('monorail.Issues', 'BulkUpdateApprovals', message).then(
      (resp) => {
        if (resp.issueRefs && resp.issueRefs.length) {
          const idsStr = Array.from(resp.issueRefs, (ref) => ref.localId).join(', ');
          this.responseMessage = `${this.getTimeStamp()}: Updated ${selectedFieldDef.fieldRef.fieldName} in issues: ${idsStr} (${resp.issueRefs.length} of ${this.issueRefs.length}).`;
          root.querySelector('form').reset();
        } else {
          this.errorMessage = NO_UPDATES_MESSAGE;
        };
        this.toggleDisableForm();
      }, (error) => {
        this.errorMessage = error;
        this.toggleDisableForm();
      });
  }

  getTimeStamp() {
    const date = new Date();
    return `${date.getHours()}:${date.getMinutes()}:${date.getSeconds()}`;
  }

  toggleDisableForm() {
    const root = this.shadowRoot;
    root.querySelectorAll('input, textarea, select, button').forEach((input) => {
      input.disabled = !input.disabled;
    });
  }
}

customElements.define(MrBulkApprovalUpdate.is, MrBulkApprovalUpdate);
