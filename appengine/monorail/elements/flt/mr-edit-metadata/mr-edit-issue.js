'use strict';

// Match: projectName:localIdFormat
const ISSUE_ID_REGEX = /([A-Za-z]+)?:?(\d+)/;

/**
 * `<mr-edit-issue>`
 *
 * Issue editing form.
 *
 */
class MrEditIssue extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-edit-issue';
  }

  static get properties() {
    return {
      issue: {
        type: Object,
        statePath: 'issue',
        observer: 'reset',
      },
      issueId: {
        type: Number,
        statePath: 'issueId',
      },
      projectName: {
        type: String,
        statePath: 'projectName',
      },
      projectConfig: {
        type: Object,
        statePath: 'projectConfig',
      },
      statuses: {
        type: Array,
        statePath: 'projectConfig.statusDefs',
      },
      updatingIssue: {
        type: Boolean,
        statePath: 'updatingIssue',
      },
      updateIssueError: {
        type: Object,
        statePath: 'updateIssueError',
      },
      _labelNames: {
        type: Array,
        computed: '_computeLabelNames(issue.labelRefs)',
      },
      _fieldDefs: {
        type: Array,
        statePath: selectors.fieldDefsForIssue,
      },
    };
  }

  reset() {
    Polymer.dom(this.root).querySelector('#metadataForm').reset();
  }

  save() {
    const form = Polymer.dom(this.root).querySelector('#metadataForm');
    const data = form.getDelta();
    data.sendEmail = form.sendEmail;
    const message = this._generateMessage(data);

    // Add files to message.
    const loads = form.loadAttachments();
    Promise.all(loads).then((uploads) => {
      if (uploads && uploads.length) {
        message.uploads = uploads;
      }

      if (message.commentContent || message.delta || message.uploads) {
        actionCreator.updateIssue(this.dispatch.bind(this), message);
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
    return labels.map((l) => l.label);
  }

  _omitEmptyDisplayName(displayName) {
    return displayName === '----' ? '' : displayName;
  }
}

customElements.define(MrEditIssue.is, MrEditIssue);
