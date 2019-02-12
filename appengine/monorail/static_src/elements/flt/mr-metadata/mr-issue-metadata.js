// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import '../../chops/chops-timestamp/chops-timestamp.js';
import {selectors} from '../../redux/selectors.js';
import {ReduxMixin, actionType} from '../../redux/redux-mixin.js';
import '../../mr-user-link/mr-user-link.js';
import '../shared/mr-flt-styles.js';
import './mr-metadata.js';

/**
 * `<mr-issue-metadata>`
 *
 * The metadata view for a single issue. Contains information such as the owner.
 *
 */
class MrIssueMetadata extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style include="mr-flt-styles">
        :host {
          box-sizing: border-box;
          padding: 0.5em 16px;
          max-width: 100%;
          display: block;
        }
        a.label {
          color: hsl(120, 100%, 25%);
          text-decoration: none;
        }
        a.label[data-derived] {
          font-style: italic;
        }
        .restricted {
          background: hsl(30, 100%, 93%);
          border: var(--chops-normal-border);
          width: 100%;
          box-sizing: border-box;
          padding: 0.5em 8px;
          margin: 1em auto;
        }
        .restricted i.material-icons {
          color: hsl(30, 5%, 39%);
          display: block;
          margin-right: 4px;
          margin-bottom: 4px;
        }
        .restricted strong {
          display: flex;
          align-items: center;
          justify-content: center;
          text-align: center;
          width: 100%;
          margin-bottom: 0.5em;
        }
        .star-line {
          width: 100%;
          text-align: center;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        /* Wrap the star icon around a button for accessibility. */
        .star-line button {
          background: none;
          border: none;
          cursor: pointer;
          padding: 0;
          margin: 0;
        }
        .star-line button[disabled] {
          opacity: 0.5;
          cursor: default;
        }
        .star-line i.material-icons {
          color: hsl(120, 5%, 66%);
        }
      </style>
      <div class="star-line">
        <button on-click="toggleStar" disabled\$="[[!_canStar]]">
          <template is="dom-if" if="[[isStarred]]">
            <i class="material-icons" title="You've starred this issue">star</i>
          </template>
          <template is="dom-if" if="[[!isStarred]]">
            <i class="material-icons" title="Click to star this issue">star_border</i>
          </template>
        </button>
        Starred by [[_renderCount(issue.starCount)]] user[[_renderPluralS(issue.starCount)]]
      </div>
      <mr-metadata
        aria-label="Issue Metadata"
        owner="[[issue.ownerRef]]"
        cc="[[issue.ccRefs]]"
        issue-status="[[issue.statusRef]]"
        components="[[_components]]"
        field-defs="[[_fieldDefs]]"
        blocked-on="[[issue.blockedOnIssueRefs]]"
        blocking="[[issue.blockingIssueRefs]]"
        merged-into="[[issue.mergedIntoIssueRef]]"
        modified-timestamp="[[issue.modifiedTimestamp]]"
      ></mr-metadata>

      <div class="labels-container">
        <template is="dom-repeat" items="[[issue.labelRefs]]" as="label">
          <a href\$="/p/[[projectName]]/issues/list?q=label:[[label.label]]" class="label" data-derived\$="[[label.isDerived]]">[[label.label]]</a>
          <br>
        </template>
      </div>
      <div class="restricted">
        <strong><i class="material-icons">lock</i>Restricted</strong>
        Only users with Google permission can see this issue.
      </div>
    `;
  }

  static get is() {
    return 'mr-issue-metadata';
  }

  static get properties() {
    return {
      issue: Object,
      issueId: Number,
      projectName: String,
      projectConfig: String,
      isStarred: {
        type: Boolean,
        value: false,
      },
      fetchingIsStarred: Boolean,
      starringIssue: Boolean,
      _components: Array,
      _fieldDefs: Array,
      _canStar: {
        type: Boolean,
        computed: '_computeCanStar(fetchingIsStarred, starringIssue)',
      },
      _type: String,
    };
  }

  static mapStateToProps(state, element) {
    return {
      issue: state.issue,
      issueId: state.issueId,
      projectName: state.projectName,
      projectConfig: state.projectConfig,
      isStarred: state.isStarred,
      fetchingIsStarred: state.fetchingIsStarred,
      starringIssue: state.starringIssue,
      _components: selectors.componentsForIssue(state),
      _fieldDefs: selectors.fieldDefsForIssue(state),
      _type: selectors.issueType(state),
    };
  }

  edit() {
    this.dispatchAction({
      type: actionType.OPEN_DIALOG,
      dialog: DialogState.EDIT_ISSUE,
    });
  }

  toggleStar() {
    if (!this._canStar) return;
    this.dispatchAction({type: actionType.STAR_ISSUE_START});

    const newIsStarred = !this.isStarred;
    const message = {
      issueRef: {
        projectName: this.projectName,
        localId: this.issueId,
      },
      starred: newIsStarred,
    };

    const starIssue = window.prpcClient.call(
      'monorail.Issues', 'StarIssue', message
    );

    starIssue.then((resp) => {
      this.dispatchAction({
        type: actionType.STAR_ISSUE_SUCCESS,
        starCount: resp.starCount,
        isStarred: newIsStarred,
      });
    }, (error) => {
      this.dispatchAction({
        type: actionType.STAR_ISSUE_FAILURE,
        error,
      });
    });
  }

  _computeCanStar(fetching, starring) {
    return !(fetching || starring);
  }

  _renderPluralS(count) {
    return count == 1 ? '' : 's';
  }

  _renderCount(count) {
    return count ? count : 0;
  }
}

customElements.define(MrIssueMetadata.is, MrIssueMetadata);
