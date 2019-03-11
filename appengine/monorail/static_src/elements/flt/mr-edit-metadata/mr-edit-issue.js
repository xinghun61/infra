// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {selectors} from '../../redux/selectors.js';
import {ReduxMixin, actionCreator} from '../../redux/redux-mixin.js';
import './mr-edit-metadata.js';
import {loadAttachments} from '../shared/flt-helpers.js';
import '../shared/mr-flt-styles.js';

// Match: projectName:localIdFormat
const ISSUE_ID_REGEX = /(?:([a-z0-9-]+):)?(\d+)/i;

/**
 * `<mr-edit-issue>`
 *
 * Issue editing form.
 *
 */
export class MrEditIssue extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style include="mr-flt-styles"></style>
      <mr-edit-metadata
        id="metadataForm"
        owner-name="[[_omitEmptyDisplayName(issue.ownerRef.displayName)]]"
        cc="[[issue.ccRefs]]"
        status="[[issue.statusRef.status]]"
        statuses="[[projectConfig.statusDefs]]"
        summary="[[issue.summary]]"
        components="[[issue.componentRefs]]"
        field-defs="[[_fieldDefs]]"
        field-values="[[issue.fieldValues]]"
        blocked-on="[[issue.blockedOnIssueRefs]]"
        blocking="[[issue.blockingIssueRefs]]"
        merged-into="[[issue.mergedIntoIssueRef]]"
        label-names="[[_labelNames]]"
        derived-labels="[[_derivedLabels]]"
        on-save="save"
        on-discard="reset"
        disabled="[[updatingIssue]]"
        error="[[updateIssueError.description]]"
      ></mr-edit-metadata>
    `;
  }

  static get is() {
    return 'mr-edit-issue';
  }

  static get properties() {
    return {
      issue: {
        type: Object,
        observer: 'reset',
      },
      issueId: Number,
      projectName: String,
      projectConfig: Object,
      updatingIssue: Boolean,
      updateIssueError: Object,
      _labelNames: {
        type: Array,
        computed: '_computeLabelNames(issue.labelRefs)',
      },
      _derivedLabels: {
        type: Array,
        computed: '_computeDerivedLabels(issue.labelRefs)',
      },
      _fieldDefs: Array,
    };
  }

  static mapStateToProps(state, element) {
    return {
      issue: state.issue,
      issueId: state.issueId,
      projectName: state.projectName,
      projectConfig: state.projectConfig,
      updatingIssue: state.requests.updateIssue.requesting,
      updateIssueError: state.requests.updateIssue.error,
      _fieldDefs: selectors.fieldDefsForIssue(state),
    };
  }

  reset() {
    this.shadowRoot.querySelector('#metadataForm').reset();
  }

  save() {
    const form = this.shadowRoot.querySelector('#metadataForm');
    const data = form.getDelta();
    data.sendEmail = form.sendEmail;
    const message = this._generateMessage(data);

    // Add files to message.
    const loads = loadAttachments(form.newAttachments);
    Promise.all(loads).then((uploads) => {
      if (uploads && uploads.length) {
        message.uploads = uploads;
      }

      if (message.commentContent || message.delta || message.uploads) {
        actionCreator.updateIssue(this.dispatchAction.bind(this), message);
      }
    }).catch((reason) => {
      console.error('loading file for attachment: ', reason);
    });
  }

  _generateMessage(data) {
    let message = {
      issueRef: {
        projectName: this.projectName,
        localId: this.issueId,
      },
    };

    if (data.sendEmail) {
      message.sendEmail = true;
    }

    let delta = {};

    if (data.comment) {
      message['commentContent'] = data.comment;
    }

    if (data.owner !== undefined) {
      delta['ownerRef'] = this._displayNameToUserRef(data.owner);
    }

    if (data.status !== undefined) {
      delta['status'] = data.status;
    }

    if (data.mergedInto === '') {
      delta['mergedIntoRef'] = {};
    } else if (data.mergedInto !== undefined) {
      delta['mergedIntoRef'] = this._issueStringToIssueRef(data.mergedInto);
    }

    if (data.summary) {
      delta['summary'] = data.summary;
    }

    const ccAdded = data.ccAdded || [];
    const ccRemoved = data.ccRemoved || [];

    if (ccAdded.length) {
      delta['ccRefsAdd'] = ccAdded.map(this._displayNameToUserRef);
    }

    if (ccRemoved.length) {
      delta['ccRefsRemove'] = ccRemoved.map(this._displayNameToUserRef);
    }

    const componentsAdded = data.componentsAdded || [];
    const componentsRemoved = data.componentsRemoved || [];

    if (componentsAdded.length) {
      delta['compRefsAdd'] = componentsAdded.map((path) => ({path}));
    }

    if (componentsRemoved.length) {
      delta['compRefsRemove'] = componentsRemoved.map((path) => ({path}));
    }

    const labelsAdded = data.labelsAdded || [];
    const labelsRemoved = data.labelsRemoved || [];

    if (labelsAdded.length) {
      delta['labelRefsAdd'] = labelsAdded.map((label) => ({label}));
    }

    if (labelsRemoved.length) {
      delta['labelRefsRemove'] = labelsRemoved.map((label) => ({label}));
    }

    const blockingAdded = data.blockingAdded || [];
    const blockingRemoved = data.blockingRemoved || [];

    if (blockingAdded.length) {
      delta['blockingRefsAdd'] = blockingAdded.map(
        this._issueStringToIssueRef.bind(this));
    }

    if (blockingRemoved.length) {
      delta['blockingRefsRemove'] = blockingRemoved.map(
        this._issueStringToIssueRef.bind(this));
    }

    const blockedOnAdded = data.blockedOnAdded || [];
    const blockedOnRemoved = data.blockedOnRemoved || [];

    if (blockedOnAdded.length) {
      delta['blockedOnRefsAdd'] = blockedOnAdded.map(
        this._issueStringToIssueRef.bind(this));
    }

    if (blockedOnRemoved.length) {
      delta['blockedOnRefsRemove'] = blockedOnRemoved.map(
        this._issueStringToIssueRef.bind(this));
    }

    const fieldValuesAdded = data.fieldValuesAdded || [];
    const fieldValuesRemoved = data.fieldValuesRemoved || [];

    if (fieldValuesAdded.length) {
      delta['fieldValsAdd'] = data.fieldValuesAdded;
    }

    if (fieldValuesRemoved.length) {
      delta['fieldValsRemove'] = data.fieldValuesRemoved;
    }

    if (Object.keys(delta).length > 0) {
      message.delta = delta;
    }

    return message;
  }

  _displayNameToUserRef(name) {
    return {'displayName': name};
  }

  _issueStringToIssueRef(idStr) {
    const matches = idStr.match(ISSUE_ID_REGEX);
    if (!matches) {
      // TODO(zhangtiff): Add proper clientside form validation.
      throw new Error('Bug has an invalid input format');
    }
    const projectName = matches[1] ? matches[1] : this.projectName;
    const localId = Number.parseInt(matches[2]);
    return {localId, projectName};
  }

  _computeLabelNames(labels) {
    if (!labels) return [];
    return labels.filter((l) => !l.isDerived).map((l) => l.label);
  }

  _computeDerivedLabels(labels) {
    if (!labels) return [];
    return labels.filter((l) => l.isDerived).map((l) => l.label);
  }

  _omitEmptyDisplayName(displayName) {
    return displayName === '----' ? '' : displayName;
  }
}

customElements.define(MrEditIssue.is, MrEditIssue);
