// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import {connectStore} from 'elements/reducers/base.js';
import 'elements/chops/chops-timestamp/chops-timestamp.js';
import 'elements/framework/links/mr-issue-link/mr-issue-link.js';
import 'elements/framework/links/mr-user-link/mr-user-link.js';

import * as issue from 'elements/reducers/issue.js';
import './mr-field-values.js';
import {HARDCODED_FIELD_GROUPS, valuesForField, fieldDefsWithGroup,
  fieldDefsWithoutGroup} from '../shared/metadata-helpers.js';

/**
 * `<mr-metadata>`
 *
 * Generalized metadata for either approvals or issues.
 *
 */
export class MrMetadata extends connectStore(LitElement) {
  static get styles() {
    return css`
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
    `;
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      ${this.approvalStatus ? html`
        <tr>
          <th>Status:</th>
          <td>
            ${this.approvalStatus}
          </td>
        </tr>
      `: ''}

      ${this.approvers && this.approvers.length ? html`
        <tr>
          <th>Approvers:</th>
          <td>
            ${this.approvers.map((approver) => html`
              <mr-user-link
                .userRef=${approver}
                showAvailabilityIcon
              ></mr-user-link>
              <br />
            `)}
          </td>
        </tr>
      `: ''}

      ${this.setter ? html`
        <th>Setter:</th>
        <td>
          <mr-user-link
            .userRef=${this.setter}
            showAvailabilityIcon
          ></mr-user-link>
        </td>
      `: ''}

      ${this.owner ? html`
        <th>Owner:</th>
        <td>
          <mr-user-link
            .userRef=${this.owner}
            showAvailabilityIcon
            showAvailabilityText
          ></mr-user-link>
        </td>
      `: ''}

      ${this.cc && this.cc.length ? html`
        <tr>
          <th>CC:</th>
          <td>
            ${this.cc.map((cc) => html`
              <mr-user-link
                .userRef=${cc}
                showAvailabilityIcon
              ></mr-user-link>
              <br />
            `)}
          </td>
        </tr>
      `: ''}
     <tr>
       <td colspan="2">
         <mr-cue cuePrefName="availability_msgs"></mr-cue>
       </td>
     </tr>

      ${this.issueStatus ? html`
        <tr>
          <th>Status:</th>
          <td>
            ${this.issueStatus.status}
            <em>
              ${this.issueStatus.meansOpen ? '(Open)' : '(Closed)'}
            </em>
          </td>
        </tr>
        ${this.issueStatus.status === 'Duplicate' ? html`
          <tr>
            <th>MergedInto:</th>
            <td>
              <mr-issue-link
                .projectName=${this.issueRef.projectName}
                .issue=${this.mergedInto}
              ></mr-issue-link>
            </td>
          </tr>
        `: ''}
      `: ''}

      ${this.components && this.components.length ? html`
        <tr>
          <th>Components:</th>
          <td>
            ${this.components.map((comp) => html`
              <a href="/p/${this.issueRef.projectName}/issues/list?q=component:${comp.path}"
                title="${comp.path}${comp.docstring ? ' = ' + comp.docstring : ''}"
              >
                ${comp.path}</a><br />
            `)}
          </td>
        </tr>
      `:''}

      ${this.modifiedTimestamp ? html`
        <tr>
          <th>Modified:</th>
          <td>
            <chops-timestamp
              .timestamp=${this.modifiedTimestamp}
              short
            ></chops-timestamp>
          </td>
        </tr>
      `:''}

      ${this._renderCustomFields()}
    `;
  }

  _renderCustomFields() {
    const grouped = fieldDefsWithGroup(this.fieldDefs,
      this.fieldGroups, this.issueType);
    const ungrouped = fieldDefsWithoutGroup(this.fieldDefs,
      this.fieldGroups, this.issueType);
    return html`
      ${grouped.map((group) => html`
        <tr>
          <th class="group-title" colspan="2">
            ${group.groupName}
          </th>
        </tr>
        ${this._renderCustomFieldList(group.fieldDefs)}
        <tr>
          <th class="group-separator" colspan="2"></th>
        </tr>
      `)}

      ${this._renderCustomFieldList(ungrouped)}
    `;
  }

  _renderCustomFieldList(fieldDefs) {
    if (!fieldDefs || !fieldDefs.length) return '';
    return fieldDefs.map((field) => {
      const fieldValues = valuesForField(
        this.fieldValueMap, field.fieldRef.fieldName) || [];
      return html`
        <tr ?hidden=${field.isNiche && !fieldValues.length}>
          <th title=${field.docstring}>${field.fieldRef.fieldName}:</th>
          <td>
            <mr-field-values
              .name=${field.fieldRef.fieldName}
              .type=${field.fieldRef.type}
              .values=${fieldValues}
              .projectName=${this.issueRef.projectName}
            ></mr-field-values>
          </td>
        </tr>
      `;
    });
  }

  static get properties() {
    return {
      approvalStatus: {type: Array},
      approvers: {type: Array},
      setter: {type: Object},
      cc: {type: Array},
      components: {type: Array},
      fieldDefs: {type: Array},
      fieldGroups: {type: Array},
      issueStatus: {type: String},
      issueType: {type: String},
      mergedInto: {type: Object},
      owner: {type: Object},
      isApproval: {type: Boolean},
      issueRef: {type: Object},
      fieldValueMap: {type: Object},
    };
  }

  constructor() {
    super();
    this.isApproval = false;
    this.fieldGroups = HARDCODED_FIELD_GROUPS;
    this.issueRef = {};
  }

  connectedCallback() {
    super.connectedCallback();
    this.setAttribute('role', 'table');
  }

  stateChanged(state) {
    this.fieldValueMap = issue.fieldValueMap(state);
    this.issueType = issue.type(state);
    this.issueRef = issue.issueRef(state);
    this.relatedIssues = issue.relatedIssues(state);
  }
}

customElements.define('mr-metadata', MrMetadata);
