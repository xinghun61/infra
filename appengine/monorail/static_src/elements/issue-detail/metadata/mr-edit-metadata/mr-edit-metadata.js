// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import debounce from 'debounce';

import 'elements/chops/chops-button/chops-button.js';
import 'elements/framework/mr-upload/mr-upload.js';
import 'elements/chops/chops-checkbox/chops-checkbox.js';
import 'elements/framework/mr-error/mr-error.js';
import 'elements/framework/mr-warning/mr-warning.js';
import {store, connectStore} from 'elements/reducers/base.js';
import {fieldTypes} from 'elements/shared/field-types.js';
import {displayNameToUserRef, labelStringToRef, componentStringToRef,
  componentRefsToStrings, issueStringToRef, issueRefToString,
  issueRefsToStrings, filteredUserDisplayNames,
} from 'elements/shared/converters.js';
import {isEmptyObject, equalsIgnoreCase} from 'elements/shared/helpers.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles.js';
import * as issue from 'elements/reducers/issue.js';
import * as project from 'elements/reducers/project.js';
import * as ui from 'elements/reducers/ui.js';
import '../mr-edit-field/mr-edit-field.js';
import '../mr-edit-field/mr-edit-status.js';
import {ISSUE_EDIT_PERMISSION} from 'elements/shared/permissions.js';
import {fieldDefsWithGroup, fieldDefsWithoutGroup,
  valuesForField} from '../shared/metadata-helpers.js';


const DEBOUNCED_PRESUBMIT_TIME_OUT = 400;

/**
 * `<mr-edit-metadata>`
 *
 * Editing form for either an approval or the overall issue.
 *
 */
export class MrEditMetadata extends connectStore(LitElement) {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          display: block;
          font-size: var(--chops-main-font-size);
        }
        :host(.edit-actions-right) .edit-actions {
          flex-direction: row-reverse;
          text-align: right;
        }
        :host(.edit-actions-right) .edit-actions chops-checkbox {
          text-align: left;
        }
        .edit-actions chops-checkbox {
          max-width: 200px;
          margin-top: 2px;
          flex-grow: 2;
          text-align: right;
        }
        .edit-actions {
          width: 100%;
          max-width: 500px;
          margin: 0.5em 0;
          text-align: left;
          display: flex;
          flex-direction: row;
          align-items: center;
        }
        .edit-actions chops-button {
          flex-grow: 0;
          flex-shrink: 0;
        }
        .edit-actions .emphasized {
          margin-left: 0;
        }
        input {
          box-sizing: border-box;
          width: var(--mr-edit-field-width);
          padding: var(--mr-edit-field-padding);
          font-size: var(--chops-main-font-size);
        }
        mr-upload {
          margin-bottom: 0.25em;
        }
        textarea {
          font-family: var(--mr-toggled-font-family);
          width: 100%;
          margin: 0.25em 0;
          box-sizing: border-box;
          border: var(--chops-accessible-border);
          height: 8em;
          transition: height 0.1s ease-in-out;
          padding: 0.5em 4px;
          grid-column-start: 1;
          grid-column-end: 2;
        }
        button.toggle {
          background: none;
          color: var(--chops-link-color);
          border: 0;
          width: 100%;
          padding: 0.25em 0;
          text-align: left;
        }
        button.toggle:hover {
          cursor: pointer;
          text-decoration: underline;
        }
        .presubmit-derived {
          color: gray;
          font-style: italic;
          text-decoration-line: underline;
          text-decoration-style: dotted;
        }
        .presubmit-derived-header {
          color: gray;
          font-weight: bold;
        }
        .discard-button {
          margin-right: 16px;
          margin-left: 16px;
        }
        .group {
          width: 100%;
          border: 1px solid hsl(0, 0%, 83%);
          grid-column: 1 / -1;
          margin: 0;
          margin-bottom: 0.5em;
          padding: 0;
          padding-bottom: 0.5em;
        }
        .group legend {
          margin-left: 130px;
        }
        .group-title {
          text-align: center;
          font-style: oblique;
          margin-top: 4px;
          margin-bottom: -8px;
        }
        i.inline-warning {
          font-size: var(--chops-icon-font-size);
          color: #FF6F00;
          vertical-align: bottom;
        }
        i.inline-info {
          font-size: var(--chops-icon-font-size);
          color: gray;
          vertical-align: bottom;
        }
      `,
    ];
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      ${this.error ? html`
        <mr-error>${this.error}</mr-error>` : ''}
      <form id="editForm">
        <textarea
          id="commentText"
          placeholder="Add a comment"
          @keyup=${this._processChanges}
          aria-label="Comment"
        ></textarea>
        <mr-upload
          ?hidden=${this.disableAttachments}
        ></mr-upload>
        <div class="input-grid">
          ${this._canEditIssue ? this._renderEditFields() : ''}
          ${this._renderPresubmitErrorsAndWarnings()}

          <span></span>
          <div class="edit-actions">
            <chops-button @click=${this.save} class="emphasized" ?disabled=${this.disabled}>
              Save changes
            </chops-button>
            <chops-button
              @click=${this.discard}
              class="de-emphasized discard-button"
              ?disabled=${this.disabled}
            >
              Discard
            </chops-button>

            <chops-checkbox
              id="sendEmail"
              @checked-change=${this._sendEmailChecked}
              ?checked=${this.sendEmail}
            >Send email</chops-checkbox>
          </div>

          ${!this.isApproval ? this._renderPresubmitChanges() : ''}
        </div>
      </form>
    `;
  }

  _renderPresubmitChanges() {
    const {derivedCcs, derivedLabels} = this.presubmitResponse || {};
    const hasCcs = derivedCcs && derivedCcs.length;
    const hasLabels = derivedLabels && derivedLabels.length;
    const hasDerivedValues = hasCcs || hasLabels;
    return html`
      ${hasDerivedValues ? html`
          <span></span>
          <div class="presubmit-derived-header">
            Filter rules and components will add
          </div>
        ` : ''}

      ${hasCcs? html`
          <label
            for="derived-ccs"
            class="presubmit-derived-header"
          >CC:</label>
          <div id="derived-ccs">
            ${derivedCcs.map((cc) => html`
              <span
                title=${cc.why}
                class="presubmit-derived"
              >${cc.value}</span>
            `)}
          </div>
        ` : ''}

      ${hasLabels ? html`
          <label
            for="derived-labels"
            class="presubmit-derived-header"
          >Labels:</label>
          <div id="derived-labels">
            ${derivedLabels.map((label) => html`
              <span
                title=${label.why}
                class="presubmit-derived"
              >${label.value}</span>
            `)}
          </div>
        ` : ''}
    `;
  }

  _renderPresubmitErrorsAndWarnings() {
    const presubmitResponse = this.presubmitResponse || {};
    const presubmitWarnings = presubmitResponse.warnings || [];
    const presubmitErrors = presubmitResponse.errors || [];
    return (presubmitWarnings.length || presubmitErrors.length) ?
      html`
        <span></span>
        <div>
          ${presubmitWarnings.map((warning) => html`
            <mr-warning title=${warning.why}>${warning.value}</mr-warning>
          `)}
          <!-- TODO(ehmaldonado): Look into blocking submission on presubmit
          -->
          ${presubmitErrors.map((error) => html`
            <mr-error title=${error.why}>${error.value}</mr-error>
          `)}
        </div>
      ` : '';
  }

  _renderEditFields() {
    if (this.isApproval) {
      return html`
        ${this._renderStatus()}
        ${this._renderApprovers()}
        ${this._renderFieldDefs()}

        ${this._renderNicheFieldToggle()}
      `;
    }

    return html`
      ${this._renderSummary()}
      ${this._renderStatus()}
      ${this._renderOwner()}
      ${this._renderCC()}
      ${this._renderComponents()}

      ${this._renderFieldDefs()}
      ${this._renderRelatedIssues()}
      ${this._renderLabels()}

      ${this._renderNicheFieldToggle()}
    `;
  }

  _renderSummary() {
    return html`
      <label for="summaryInput">Summary:</label>
      <input
        id="summaryInput"
        value=${this.summary}
        @keyup=${this._processChanges}
      />
    `;
  }

  _renderOwner() {
    const ownerPresubmit = this._ownerPresubmit;
    return html`
      <label for="ownerInput" @click=${this._clickLabelForCustomInput}>
        ${ownerPresubmit.message ? html`
          <i
            class=${`material-icons inline-${ownerPresubmit.icon}`}
            title=${ownerPresubmit.message}
          >${ownerPresubmit.icon}</i>
        ` : ''}
        Owner:
      </label>
      <mr-edit-field
        id="ownerInput"
        .name=${'Owner'}
        .type=${'USER_TYPE'}
        .initialValues=${this.ownerName ? [this.ownerName] : []}
        .acType=${'owner'}
        .placeholder=${ownerPresubmit.placeholder}
        @change=${this._processChanges}
      ></mr-edit-field>
    `;
  }

  _renderCC() {
    return html`
      <label for="ccInput" @click=${this._clickLabelForCustomInput}>CC:</label>
      <mr-edit-field
        id="ccInput"
        .name=${'CC'}
        .type=${'USER_TYPE'}
        .initialValues=${this._ccNames}
        .derivedValues=${this._derivedCCs}
        .acType=${'member'}
        @change=${this._processChanges}
        multi
      ></mr-edit-field>
    `;
  }

  _renderComponents() {
    return html`
      <label for="componentsInput" @click=${this._clickLabelForCustomInput}>Components:</label>
      <mr-edit-field
        id="componentsInput"
        .name=${'component'}
        .type=${'STR_TYPE'}
        .initialValues=${componentRefsToStrings(this.components)}
        .acType=${'component'}
        @change=${this._processChanges}
        multi
      ></mr-edit-field>
    `;
  }

  _renderApprovers() {
    return this.hasApproverPrivileges && this.isApproval ? html`
      <label for="approversInput" @click=${this._clickLabelForCustomInput}>Approvers:</label>
      <mr-edit-field
        id="approversInput"
        .type=${'USER_TYPE'}
        .initialValues=${filteredUserDisplayNames(this.approvers)}
        .name=${'approver'}
        .acType=${'member'}
        @change=${this._processChanges}
        multi
      ></mr-edit-field>
    ` : '';
  }

  _renderStatus() {
    return this.statuses && this.statuses.length ? html`
      <label for="statusInput">Status:</label>

      <mr-edit-status
        id="statusInput"
        .status=${this.status}
        .statuses=${this.statuses}
        .mergedInto=${issueRefToString(this.mergedInto, this.projectName)}
        ?isApproval=${this.isApproval}
        @change=${this._processChanges}
      ></mr-edit-status>
    ` : '';
  }

  _renderFieldDefs() {
    return html`
      ${fieldDefsWithGroup(this.fieldDefs).map((group) => html`
        <fieldset class="group">
          <legend>${group.groupName}</legend>
          <div class="input-grid">
            ${group.fieldDefs.map((field) => this._renderCustomField(field))}
          </div>
        </fieldset>
      `)}

      ${fieldDefsWithoutGroup(this.fieldDefs).map((field) => this._renderCustomField(field))}
    `;
  }

  _renderRelatedIssues() {
    return html`
      <label for="blockedOnInput" @click=${this._clickLabelForCustomInput}>BlockedOn:</label>
      <mr-edit-field
        id="blockedOnInput"
        .initialValues=${issueRefsToStrings(this.blockedOn, this.projectName)}
        .name=${'blockedOn'}
        @change=${this._processChanges}
        multi
      ></mr-edit-field>

      <label for="blockingInput" @click=${this._clickLabelForCustomInput}>Blocking:</label>
      <mr-edit-field
        id="blockingInput"
        .initialValues=${issueRefsToStrings(this.blocking, this.projectName)}
        .name=${'blocking'}
        @change=${this._processChanges}
        multi
      ></mr-edit-field>
    `;
  }

  _renderLabels() {
    return html`
      <label for="labelsInput" @click=${this._clickLabelForCustomInput}>Labels:</label>
      <mr-edit-field
        id="labelsInput"
        .acType=${'label'}
        .initialValues=${this.labelNames}
        .derivedValues=${this.derivedLabels}
        .name=${'labels'}
        @change=${this._processChanges}
        multi
      ></mr-edit-field>
    `;
  }

  _renderCustomField(field) {
    if (!field || !field.fieldRef) return '';
    const {fieldRef, isNiche, docstring, isMultivalued} = field;
    const isHidden = !this.showNicheFields && isNiche;

    let acType;
    if (fieldRef.type === fieldTypes.USER_TYPE) {
      acType = isMultivalued ? 'member' : 'owner';
    }
    return html`
      <label
        ?hidden=${isHidden}
        for=${this._idForField(fieldRef.fieldName)}
        @click=${this._clickLabelForCustomInput}
        title=${docstring}
      >
        ${fieldRef.fieldName}:
      </label>
      <mr-edit-field
        ?hidden=${isHidden}
        id=${this._idForField(fieldRef.fieldName)}
        .name=${fieldRef.fieldName}
        .type=${fieldRef.type}
        .options=${this._optionsForField(this.optionsPerEnumField, this.fieldValueMap, fieldRef.fieldName, this.phaseName)}
        .initialValues=${valuesForField(this.fieldValueMap, fieldRef.fieldName, this.phaseName)}
        .acType=${acType}
        ?multi=${isMultivalued}
        @change=${this._processChanges}
      ></mr-edit-field>
    `;
  }

  _renderNicheFieldToggle() {
    return this._nicheFieldCount ? html`
      <span></span>
      <button type="button" class="toggle" @click=${this.toggleNicheFields}>
        <span ?hidden=${this.showNicheFields}>
          Show all fields (${this._nicheFieldCount} currently hidden)
        </span>
        <span ?hidden=${!this.showNicheFields}>
          Hide niche fields (${this._nicheFieldCount} currently shown)
        </span>
      </button>
    ` : '';
  }

  static get properties() {
    return {
      fieldDefs: {type: Array},
      formName: {type: String},
      approvers: {type: Array},
      setter: {type: Object},
      summary: {type: String},
      cc: {type: Array},
      components: {type: Array},
      status: {type: String},
      statuses: {type: Array},
      blockedOn: {type: Array},
      blocking: {type: Array},
      mergedInto: {type: Object},
      ownerName: {type: String},
      labelNames: {type: Array},
      derivedLabels: {type: Array},
      phaseName: {type: String},
      projectConfig: {type: Object},
      projectName: {type: String},
      isApproval: {type: Boolean},
      issuePermissions: {type: Object},
      hasApproverPrivileges: {type: Boolean},
      showNicheFields: {type: Boolean},
      disabled: {type: Boolean},
      disableAttachments: {type: Boolean},
      error: {type: String},
      sendEmail: {type: Boolean},
      presubmitResponse: {type: Object},
      fieldValueMap: {type: Object},
      issueType: {type: String},
      optionsPerEnumField: {type: String},
      _debouncedProcessChanges: {type: Object},
    };
  }

  constructor() {
    super();
    this.summary = '';
    this.ownerName = '';
    this.sendEmail = true;
    this.mergedInto = {};
  }

  get _nicheFieldCount() {
    const fieldDefs = this.fieldDefs || [];
    return fieldDefs.reduce((acc, fd) => acc + (fd.isNiche | 0), 0);
  }

  get _canEditIssue() {
    const issuePermissions = this.issuePermissions || [];
    return issuePermissions.includes(ISSUE_EDIT_PERMISSION);
  }

  get _ccNames() {
    const users = this.cc || [];
    return filteredUserDisplayNames(users.filter((u) => !u.isDerived));
  }

  get _derivedCCs() {
    const users = this.cc || [];
    return filteredUserDisplayNames(users.filter((u) => u.isDerived));
  }

  get _ownerPresubmit() {
    const response = this.presubmitResponse;
    if (!response) return {};

    const ownerView = {message: '', placeholder: '', icon: ''};

    if (response.ownerAvailability) {
      ownerView.message = response.ownerAvailability;
      ownerView.icon = 'warning';
    } else if (response.derivedOwners && response.derivedOwners.length) {
      ownerView.placeholder = response.derivedOwners[0].value;
      ownerView.message = response.derivedOwners[0].why;
      ownerView.icon = 'info';
    }
    return ownerView;
  }

  stateChanged(state) {
    this.fieldValueMap = issue.fieldValueMap(state);
    this.issueType = issue.type(state);
    this.presubmitResponse = issue.presubmitResponse(state);
    this.projectConfig = project.project(state).config;
    this.projectName = issue.issueRef(state).projectName;
    this.issuePermissions = issue.permissions(state);
    this.optionsPerEnumField = project.optionsPerEnumField(state);
  }

  disconnectedCallback() {
    super.disconnectedCallback();

    if (this._debouncedProcessChanges) {
      this._debouncedProcessChanges.clear();
    }

    store.dispatch(ui.reportDirtyForm(this.formName, false));
  }

  async reset() {
    await this.updateComplete;
    this.shadowRoot.querySelector('#editForm').reset();
    const statusInput = this.shadowRoot.querySelector('#statusInput');
    if (statusInput) {
      statusInput.reset();
    }

    // Since custom elements containing <input> elements have the inputs
    // wrapped in ShadowDOM, those inputs don't get reset with the rest of
    // the form. Haven't been able to figure out a way to replicate form reset
    // behavior with custom input elements.
    if (this.isApproval) {
      if (this.hasApproverPrivileges) {
        const approversInput = this.shadowRoot.querySelector(
          '#approversInput');
        if (approversInput) {
          approversInput.reset();
        }
      }
    }
    this.shadowRoot.querySelectorAll('mr-edit-field').forEach((el) => {
      el.reset();
    });

    const uploader = this.shadowRoot.querySelector('mr-upload');
    if (uploader) {
      uploader.reset();
    }

    this._processChanges();
  }

  save() {
    this.dispatchEvent(new CustomEvent('save'));
  }

  discard() {
    const isDirty = this.getCommentContent() || !isEmptyObject(this.getDelta());
    if (!isDirty || confirm('Discard your changes?')) {
      this.dispatchEvent(new CustomEvent('discard'));
    }
  }

  async focus() {
    await this.updateComplete;
    this.shadowRoot.querySelector('#commentText').focus();
  }

  getCommentContent() {
    return this.shadowRoot.querySelector('#commentText').value;
  }

  async getAttachments() {
    try {
      return await this.shadowRoot.querySelector('mr-upload').loadFiles();
    } catch (e) {
      this.error = `Error while loading file for attachment: ${e.message}`;
    }
  }

  getDelta() {
    if (!this._canEditIssue) return {};

    const result = {};
    const root = this.shadowRoot;

    const statusInput = root.querySelector('#statusInput');
    if (statusInput) {
      Object.assign(result, statusInput.getDelta(this.projectName));
    }

    if (this.isApproval) {
      if (this.hasApproverPrivileges) {
        this._addListChangesToDelta(
          result, 'approversInput', 'approverRefsAdd', 'approverRefsRemove',
          displayNameToUserRef);
      }
    } else {
      // TODO(zhangtiff): Consider representing baked-in fields such as owner,
      // cc, and status similarly to custom fields to reduce repeated code.

      const summaryInput = root.querySelector('#summaryInput');
      if (summaryInput) {
        const newSummary = summaryInput.value;
        if (newSummary !== this.summary) {
          result.summary = newSummary;
        }
      }

      const ownerInput = root.querySelector('#ownerInput');
      if (ownerInput) {
        const newOwner = ownerInput.getValue();
        if (newOwner !== this.ownerName) {
          result.ownerRef = displayNameToUserRef(newOwner);
        }
      }

      this._addListChangesToDelta(result, 'labelsInput',
        'labelRefsAdd', 'labelRefsRemove', labelStringToRef);

      this._addListChangesToDelta(result, 'ccInput',
        'ccRefsAdd', 'ccRefsRemove', displayNameToUserRef);

      this._addListChangesToDelta(result, 'componentsInput',
        'compRefsAdd', 'compRefsRemove', componentStringToRef);

      this._addListChangesToDelta(result, 'blockedOnInput',
        'blockedOnRefsAdd', 'blockedOnRefsRemove',
        issueStringToRef.bind(null, this.projectName));

      this._addListChangesToDelta(result, 'blockingInput',
        'blockingRefsAdd', 'blockingRefsRemove',
        issueStringToRef.bind(null, this.projectName));
    }

    const fieldDefs = this.fieldDefs || [];
    fieldDefs.forEach(({fieldRef}) => {
      const fieldNameInput = this._idForField(fieldRef.fieldName);
      this._addListChangesToDelta(
        result, fieldNameInput, 'fieldValsAdd', 'fieldValsRemove',
        (v) => {
          return {
            fieldRef: {
              fieldName: fieldRef.fieldName,
              fieldId: fieldRef.fieldId,
            },
            value: v,
          };
        }
      );
    });

    return result;
  }

  toggleNicheFields() {
    this.showNicheFields = !this.showNicheFields;
  }

  _processChanges() {
    if (!this._debouncedProcessChanges) {
      this._debouncedProcessChanges = debounce(() => {
        // Don't run this functionality if the element has disconnected.
        if (!this.isConnected) return;

        const delta = this.getDelta();
        const commentContent = this.getCommentContent();
        store.dispatch(ui.reportDirtyForm(
          this.formName, !isEmptyObject(delta) || Boolean(commentContent)));
        this.dispatchEvent(new CustomEvent('change', {detail: {delta}}));
      }, DEBOUNCED_PRESUBMIT_TIME_OUT);
    }
    this._debouncedProcessChanges();
  }

  _addListChangesToDelta(delta, inputId, addedKey, removedKey, mapFn) {
    const root = this.shadowRoot;
    const input = root.querySelector(`#${inputId}`);
    if (!input) return;
    const valuesAdded = input.getValuesAdded();
    const valuesRemoved = input.getValuesRemoved();
    if (valuesAdded && valuesAdded.length) {
      delta[addedKey] = valuesAdded.map(mapFn);
    }
    if (valuesRemoved && valuesRemoved.length) {
      delta[removedKey] = valuesRemoved.map(mapFn);
    }
  }

  // This function exists because <label for="inputId"> doesn't work for custom
  // input elements.
  _clickLabelForCustomInput(e) {
    const target = e.target;
    const forValue = target.getAttribute('for');
    if (forValue) {
      const customInput = this.shadowRoot.querySelector('#' + forValue);
      if (customInput && customInput.focus) {
        customInput.focus();
      }
    }
  }

  _idForField(name) {
    return `${name}Input`;
  }


  _optionsForField(optionsPerEnumField, fieldValueMap, fieldName, phaseName) {
    if (!optionsPerEnumField || !fieldName) return [];
    const key = fieldName.toLowerCase();
    if (!optionsPerEnumField.has(key)) return [];
    const options = [...optionsPerEnumField.get(key)];
    const values = valuesForField(fieldValueMap, fieldName, phaseName);
    values.forEach((v) => {
      const optionExists = options.find(
        (opt) => equalsIgnoreCase(opt.optionName, v));
      if (!optionExists) {
        // Note that enum fields which are not explicitly defined can be set,
        // such as in the case when an issue is moved.
        options.push({optionName: v});
      }
    });
    return options;
  }

  _sendEmailChecked(evt) {
    this.sendEmail = evt.detail.checked;
  }
}

customElements.define('mr-edit-metadata', MrEditMetadata);