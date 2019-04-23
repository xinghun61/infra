// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {Debouncer} from '@polymer/polymer/lib/utils/debounce.js';
import {timeOut} from '@polymer/polymer/lib/utils/async.js';

import '../../chops/chops-button/chops-button.js';
import '../../framework/mr-upload/mr-upload.js';
import '../../chops/chops-checkbox/chops-checkbox.js';
import '../../mr-error/mr-error.js';
import '../../mr-warning/mr-warning.js';
import {store} from '../../redux/base.js';
import {fieldTypes} from '../../shared/field-types.js';
import {displayNameToUserRef, labelStringToRef, componentStringToRef,
  issueStringToRef, issueRefToString} from '../../shared/converters.js';
import {isEmptyObject, equalsIgnoreCase} from '../../shared/helpers.js';
import '../../shared/mr-shared-styles.js';
import {MetadataMixin} from '../shared/metadata-mixin.js';
import * as issue from '../../redux/issue.js';
import * as project from '../../redux/project.js';
import * as ui from '../../redux/ui.js';
import '../mr-edit-field/mr-edit-field.js';
import '../mr-edit-field/mr-edit-status.js';
import {ISSUE_EDIT_PERMISSION} from '../../shared/permissions.js';


/**
 * `<mr-edit-metadata>`
 *
 * Editing form for either an approval or the overall issue.
 *
 */
export class MrEditMetadata extends MetadataMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <style include="mr-shared-styles">
        :host {
          display: block;
          font-size: var(--chops-main-font-size);
          --mr-edit-field-styles: {
            box-sizing: border-box;
            width: 95%;
            padding: 0.25em 4px;
            font-size: var(--chops-main-font-size);
          }
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
          @apply --mr-edit-field-styles;
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
      </style>
      <template is="dom-if" if="[[error]]">
        <mr-error>[[error]]</mr-error>
      </template>
      <form id="editForm">
        <textarea
          id="commentText"
          placeholder="Add a comment"
          on-keyup="_onChange"
          aria-label="Comment"
        ></textarea>
        <mr-upload
          hidden$="[[disableAttachments]]"
        ></mr-upload>
        <div class="input-grid">
          <template is="dom-if" if="[[_canEditIssue]]">
            <template is="dom-if" if="[[!isApproval]]">
              <label for="summaryInput">Summary:</label>
              <input
                id="summaryInput"
                value$="[[summary]]"
                on-keyup="_onChange"
              />
            </template>
            <template is="dom-if" if="[[statuses.length]]">
              <label for="statusInput">Status:</label>

              <mr-edit-status
                id="statusInput"
                status="[[status]]"
                statuses="[[statuses]]"
                is-approval="[[isApproval]]"
                merged-into="[[_computeMergedIntoString(projectName, mergedInto)]]"
                on-change="_onChange"
              ></mr-edit-status>
            </template>


            <template is="dom-if" if="[[!isApproval]]">
              <label for="ownerInput" on-click="_clickLabelForCustomInput">
                <template is="dom-if" if="[[_ownerMessage]]">
                  <i
                    class$="material-icons inline-[[_ownerIcon]]"
                    title="[[_ownerMessage]]"
                  >[[_ownerIcon]]</i>
                </template>
                Owner:
              </label>
              <mr-edit-field
                id="ownerInput"
                name="Owner"
                type="USER_TYPE"
                initial-values="[[_wrapList(ownerName)]]"
                ac-type="owner"
                placeholder="[[_ownerPlaceholder]]"
                on-change="_onChange"
              ></mr-edit-field>

              <label for="ccInput" on-click="_clickLabelForCustomInput">CC:</label>
              <mr-edit-field
                id="ccInput"
                name="CC"
                type="USER_TYPE"
                initial-values="[[_ccNames]]"
                derived-values="[[_derivedCCs]]"
                ac-type="member"
                on-change="_onChange"
                multi
              ></mr-edit-field>

              <label for="componentsInput" on-click="_clickLabelForCustomInput">Components:</label>
              <mr-edit-field
                id="componentsInput"
                name="component"
                type="STR_TYPE"
                initial-values="[[_mapComponentRefsToNames(components)]]"
                ac-type="component"
                on-change="_onChange"
                multi
              ></mr-edit-field>
            </template>

            <template is="dom-if" if="[[_and(hasApproverPrivileges, isApproval)]]">
              <label for="approversInput" on-click="_clickLabelForCustomInput">Approvers:</label>
              <mr-edit-field
                id="approversInput"
                type="USER_TYPE"
                initial-values="[[_mapUserRefsToNames(approvers)]]"
                ac-type="member"
                name="approver"
                on-change="_onChange"
                multi
              ></mr-edit-field>
            </template>

            <template is="dom-repeat" items="[[_fieldDefsWithGroups]]" as="group">
              <fieldset class="group">
                <legend>[[group.groupName]]</legend>
                <div class="input-grid">
                  <template is="dom-repeat" items="[[group.fieldDefs]]" as="field">
                    <label
                      hidden$="[[_fieldIsHidden(showNicheFields, field.isNiche)]]"
                      for$="[[_idForField(field.fieldRef.fieldName)]]"
                      on-click="_clickLabelForCustomInput"
                      title$="[[field.docstring]]"
                    >
                      [[field.fieldRef.fieldName]]:
                    </label>
                    <mr-edit-field
                      hidden$="[[_fieldIsHidden(showNicheFields, field.isNiche)]]"
                      id$="[[_idForField(field.fieldRef.fieldName)]]"
                      name="[[field.fieldRef.fieldName]]"
                      type="[[field.fieldRef.type]]"
                      options="[[_optionsForField(optionsPerEnumField, fieldValueMap, field.fieldRef.fieldName, phaseName)]]"
                      initial-values="[[_valuesForField(fieldValueMap, field.fieldRef.fieldName, phaseName)]]"
                      ac-type="[[_computeAcType(field.fieldRef.type, field.isMultivalued)]]"
                      multi="[[field.isMultivalued]]"
                      on-change="_onChange"
                    ></mr-edit-field>
                  </template>
                </div>
              </fieldset>
            </template>

            <template is="dom-repeat" items="[[_fieldDefsWithoutGroup]]" as="field">
              <label
                hidden$="[[_fieldIsHidden(showNicheFields, field.isNiche)]]"
                for$="[[_idForField(field.fieldRef.fieldName)]]"
                on-click="_clickLabelForCustomInput"
                title$="[[field.docstring]]"
              >
                [[field.fieldRef.fieldName]]:
              </label>
              <mr-edit-field
                hidden$="[[_fieldIsHidden(showNicheFields, field.isNiche)]]"
                id$="[[_idForField(field.fieldRef.fieldName)]]"
                name="[[field.fieldRef.fieldName]]"
                type="[[field.fieldRef.type]]"
                options="[[_optionsForField(optionsPerEnumField, fieldValueMap, field.fieldRef.fieldName, phaseName)]]"
                initial-values="[[_valuesForField(fieldValueMap, field.fieldRef.fieldName, phaseName)]]"
                ac-type="[[_computeAcType(field.fieldRef.type, field.isMultivalued)]]"
                multi="[[field.isMultivalued]]"
                on-change="_onChange"
              ></mr-edit-field>
            </template>

            <template is="dom-if" if="[[!isApproval]]">
              <label for="blockedOnInput" on-click="_clickLabelForCustomInput">BlockedOn:</label>
              <mr-edit-field
                id="blockedOnInput"
                initial-values="[[_mapBlockerRefsToIdStrings(blockedOn, projectName)]]"
                name="blockedOn"
                on-change="_onChange"
                multi
              ></mr-edit-field>

              <label for="blockingInput" on-click="_clickLabelForCustomInput">Blocking:</label>
              <mr-edit-field
                id="blockingInput"
                initial-values="[[_mapBlockerRefsToIdStrings(blocking, projectName)]]"
                name="blocking"
                on-change="_onChange"
                multi
              ></mr-edit-field>

              <label for="labelsInput" on-click="_clickLabelForCustomInput">Labels:</label>
              <mr-edit-field
                id="labelsInput"
                ac-type="label"
                initial-values="[[labelNames]]"
                derived-values="[[derivedLabels]]"
                name="labels"
                on-change="_onChange"
                multi
              ></mr-edit-field>
            </template>

            <span hidden$="[[!_nicheFieldCount]]"></span>
            <button type="button" class="toggle" on-click="toggleNicheFields" hidden$="[[!_nicheFieldCount]]">
              <span hidden$="[[showNicheFields]]">
                Show all fields ([[_nicheFieldCount]] currently hidden)
              </span>
              <span hidden$="[[!showNicheFields]]">
                Hide niche fields ([[_nicheFieldCount]] currently shown)
              </span>
            </button>
          </template>

          <template is="dom-if" if="[[_hasErrorsOrWarnings]]">
            <span></span>
            <div id="presubmit-errors-and-warnings">
              <template is="dom-repeat" items="[[presubmitResponse.warnings]]">
                <mr-warning title="[[item.why]]">[[item.value]]</mr-warning>
              </template>
              <!-- TODO(ehmaldonado): Look into blocking submission on presubmit
              -->
              <template is="dom-repeat" items="[[presubmitResponse.errors]]">
                <mr-error title="[[item.why]]">[[item.value]]</mr-error>
              </template>
            </div>
          </template>

          <span></span>
          <div class="edit-actions">
            <chops-button on-click="save" class="emphasized" disabled="[[disabled]]">
              Save changes
            </chops-button>
            <chops-button
              on-click="discard"
              class="de-emphasized discard-button"
              disabled="[[disabled]]"
            >
              Discard
            </chops-button>

            <chops-checkbox
              id="sendEmail"
              on-checked-change="_sendEmailChecked"
              checked="[[sendEmail]]"
            >Send email</chops-checkbox>
          </div>

          <template is="dom-if" if="[[!isApproval]]">
            <template is="dom-if" if="[[_hasDerivedValues]]">
              <span></span>
              <div class="presubmit-derived-header">
                Filter rules and components will add
              </div>
            </template>

            <template is="dom-if" if="[[presubmitResponse.derivedCcs]]">
              <label
                for="derived-ccs"
                class="presubmit-derived-header"
              >CC:</label>
              <div id="derived-ccs">
                <template
                  is="dom-repeat"
                  items="[[presubmitResponse.derivedCcs]]"
                >
                  <span
                    title="[[item.why]]"
                    class="presubmit-derived"
                  >[[item.value]]</span>
                </template>
              </div>
            </template>

            <template is="dom-if" if="[[presubmitResponse.derivedLabels]]">
              <label
                for="derived-labels"
                class="presubmit-derived-header"
              >Labels:</label>
              <div id="derived-labels">
                <template
                  is="dom-repeat"
                  items="[[presubmitResponse.derivedLabels]]"
                >
                  <span
                    title="[[item.why]]"
                    class="presubmit-derived"
                  >[[item.value]]</span>
                </template>
              </div>
            </template>
          </template>
        </div>
      </form>
    `;
  }

  static get is() {
    return 'mr-edit-metadata';
  }

  static get properties() {
    return {
      formName: String,
      approvers: {
        type: Array,
        value: () => [],
      },
      setter: {
        type: Object,
        value: () => {},
      },
      summary: {
        type: String,
        value: '',
      },
      cc: {
        type: Array,
        value: () => [],
      },
      components: {
        type: Array,
        value: () => [],
      },
      status: String,
      statuses: {
        type: Array,
        value: () => [],
      },
      blockedOn: {
        type: Array,
        value: () => [],
      },
      blocking: {
        type: Array,
        value: () => [],
      },
      mergedInto: Object,
      ownerName: {
        type: String,
        value: '',
      },
      labelNames: {
        type: Array,
        value: () => [],
      },
      derivedLabels: {
        type: Array,
        value: [],
      },
      phaseName: String,
      projectConfig: Object,
      projectName: String,
      isApproval: {
        type: Boolean,
        value: false,
      },
      issuePermissions: Object,
      hasApproverPrivileges: {
        type: Boolean,
        value: false,
      },
      showNicheFields: {
        type: Boolean,
        value: false,
      },
      disabled: {
        type: Boolean,
        value: false,
      },
      disableAttachments: {
        type: Boolean,
        value: false,
      },
      error: String,
      sendEmail: {
        type: Boolean,
        value: true,
      },
      presubmitResponse: {
        type: Object,
        observer: '_onPresubmitResponse',
      },
      fieldValueMap: Object, // Set by MetadataMixin.
      optionsPerEnumField: Object,
      _hasDerivedValues: Boolean,
      _hasErrorsOrWarnings: Boolean,
      _ownerIcon: String,
      _ownerMessage: String,
      _ownerPlaceholder: String,
      _nicheFieldCount: {
        type: Boolean,
        computed: '_computeNicheFieldCount(fieldDefs)',
      },
      _ccNames: {
        type: Array,
        computed: '_computeCCNames(cc)',
      },
      _derivedCCs: {
        type: Array,
        computed: '_computeDerivedCCs(cc)',
      },
      _canEditIssue: {
        type: Boolean,
        computed: '_computeCanEditIssue(issuePermissions)',
      },
      _debouncedOnChange: Object,
    };
  }

  stateChanged(state) {
    super.stateChanged(state);
    this.setProperties({
      presubmitResponse: issue.presubmitResponse(state),
      projectConfig: project.project(state).config,
      projectName: issue.issueRef(state).projectName,
      issuePermissions: issue.permissions(state),
      optionsPerEnumField: project.optionsPerEnumField(state),
    });
  }

  disconnectedCallback() {
    super.disconnectedCallback();

    if (this._debouncedOnChange) {
      this._debouncedOnChange.cancel();
    }

    store.dispatch(ui.reportDirtyForm(this.formName, false));
  }

  reset() {
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

    this._onChange();
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

  focus() {
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
    fieldDefs.forEach((field) => {
      const fieldNameInput = this._idForField(field.fieldRef.fieldName);
      this._addListChangesToDelta(
        result, fieldNameInput, 'fieldValsAdd', 'fieldValsRemove',
        (v) => {
          return {
            fieldRef: {
              fieldName: field.fieldRef.fieldName,
              fieldId: field.fieldRef.fieldId,
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

  _onChange() {
    this._debouncedOnChange = Debouncer.debounce(
      this._debouncedOnChange,
      timeOut.after(400),
      () => {
        // Don't run this functionality if the element has disconnected.
        if (!this.isConnected) return;
        const delta = this.getDelta();
        const commentContent = this.getCommentContent();
        store.dispatch(ui.reportDirtyForm(
          this.formName, !isEmptyObject(delta) || Boolean(commentContent)));
        this.dispatchEvent(new CustomEvent('change', {detail: {delta}}));
      });
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

  _computeNicheFieldCount(fieldDefs) {
    return fieldDefs.reduce((acc, fd) => acc + (fd.isNiche | 0), 0);
  }

  _mapBlockerRefsToIdStrings(arr, projectName) {
    if (!arr || !arr.length) return [];
    return arr.map((ref) => issueRefToString(ref, projectName));
  }

  // For simulating && in templating.
  _and(a, b) {
    return a && b;
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

  _computeCanEditIssue(issuePermissions) {
    return (issuePermissions || []).includes(ISSUE_EDIT_PERMISSION);
  }

  _computeCCNames(users) {
    if (!users) return [];
    return this._mapUserRefsToNames(users.filter((u) => !u.isDerived));
  }

  _computeDerivedCCs(users) {
    if (!users) return [];
    return this._mapUserRefsToNames(users.filter((u) => u.isDerived));
  }

  _mapUserRefsToNames(users) {
    if (!users) return [];
    return users.filter((u) => u.userId).map((u) => (u.displayName));
  }

  _mapComponentRefsToNames(components) {
    if (!components) return [];
    return components.map((c) => c.path);
  }

  _optionsForField(optionsPerEnumField, fieldValueMap, fieldName, phaseName) {
    if (!optionsPerEnumField || !fieldName) return [];
    const key = fieldName.toLowerCase();
    if (!optionsPerEnumField.has(key)) return [];
    const options = [...optionsPerEnumField.get(key)];
    const values = this._valuesForField(fieldValueMap, fieldName, phaseName);
    values.forEach((v) => {
      const optionExists = options.find(
        (opt) => equalsIgnoreCase(opt.optionName, v));
      if (!optionExists) {
        options.push({optionName: v});
      }
    });
    return options;
  }

  _fieldIsHidden(showNicheFields, isNiche) {
    return !showNicheFields && isNiche;
  }

  _wrapList(item) {
    if (!item) return [];
    return [item];
  }

  _sendEmailChecked(evt) {
    this.sendEmail = evt.detail.checked;
  }

  // Needed because Polymer doesn't accept non member functions.
  // TODO(ehmaldonado): Remove
  _computeMergedIntoString(projectName, ref) {
    return [issueRefToString(ref, projectName)];
  }

  _onPresubmitResponse(response) {
    this._hasDerivedValues =
      (response.derivedCcs && response.derivedCcs.length)
      || (response.derivedLabels && response.derivedLabels.length);
    this._hasErrorsOrWarnings =
      (response.errors && response.errors.length)
      || (response.warnings && response.warnings.length);
    this._ownerMessage = '';
    this._ownerPlaceholder = '';
    if (response.ownerAvailability) {
      this._ownerMessage = response.ownerAvailability;
      this._ownerIcon = 'warning';
    } else if (response.derivedOwners && response.derivedOwners.length) {
      this._ownerPlaceholder = response.derivedOwners[0].value;
      this._ownerMessage = response.derivedOwners[0].why;
      this._ownerIcon = 'info';
    }
  }

  _computeAcType(type, multi) {
    if (type === fieldTypes.USER_TYPE) {
      return multi ? 'member' : 'owner';
    }
    return '';
  }
}

customElements.define(MrEditMetadata.is, MrEditMetadata);
