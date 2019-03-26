// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../chops/chops-timestamp/chops-timestamp.js';
import {ReduxMixin, actionCreator} from
  '../../redux/redux-mixin.js';
import * as issue from '../../redux/issue.js';
import * as project from '../../redux/project.js';
import * as user from '../../redux/user.js';
import '../../links/mr-user-link/mr-user-link.js';
import '../../links/mr-hotlist-link/mr-hotlist-link.js';
import '../../shared/mr-shared-styles.js';
import './mr-metadata.js';

/**
 * `<mr-issue-metadata>`
 *
 * The metadata view for a single issue. Contains information such as the owner.
 *
 */
export class MrIssueMetadata extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style include="mr-shared-styles">
        :host {
          box-sizing: border-box;
          padding: 0.25em 8px;
          max-width: 100%;
          display: block;
        }
        h3 {
          display: block;
          font-size: 12px;
          margin: 0;
          line-height: 160%;
          width: 40%;
          height: 100%;
          overflow: ellipsis;
          flex-grow: 0;
          flex-shrink: 0;
        }
        a.label {
          color: hsl(120, 100%, 25%);
          text-decoration: none;
        }
        a.label[data-derived] {
          font-style: italic;
        }
        button.linkify {
          display: flex;
          align-items: center;
          text-decoration: none;
          padding: 0.25em 0;
        }
        button.linkify i.material-icons {
          margin-right: 4px;
          font-size: 20px;
        }
        mr-hotlist-link {
          text-overflow: ellipsis;
          overflow: hidden;
          display: block;
          width: 100%;
        }
        .bottom-section-cell, .labels-container {
          padding: 0.5em 4px;
          width: 100%;
          box-sizing: border-box;
        }
        .bottom-section-cell {
          display: flex;
          flex-direction: row;
          flex-wrap: nowrap;
          align-items: flex-start;
        }
        .bottom-section-content {
          max-width: 60%;
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
          margin-right: 4px;
        }
        .star-line button[disabled] {
          opacity: 0.5;
          cursor: default;
        }
        .star-line i.material-icons {
          color: hsl(120, 5%, 66%);
        }
        .star-line i.material-icons.starred {
          color: cornflowerblue;
        }
      </style>
      <div class="star-line">
        <button on-click="toggleStar" disabled\$="[[!_canStar]]">
          <template is="dom-if" if="[[isStarred]]">
            <i class="material-icons starred" title="You've starred this issue">star</i>
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
        merged-into="[[mergedInto]]"
        modified-timestamp="[[issue.modifiedTimestamp]]"
      ></mr-metadata>

      <div class="labels-container">
        <template is="dom-repeat" items="[[issue.labelRefs]]" as="label">
          <a href\$="/p/[[projectName]]/issues/list?q=label:[[label.label]]" class="label" data-derived\$="[[label.isDerived]]">[[label.label]]</a>
          <br>
        </template>
      </div>

      <template is="dom-if" if="[[sortedBlockedOn.length]]">
        <div class="bottom-section-cell">
          <h3>BlockedOn:</h3>
            <div class="bottom-section-content">
            <template is="dom-repeat" items="[[sortedBlockedOn]]">
              <mr-issue-link
                project-name="[[projectName]]"
                issue="[[item]]"
              >
              </mr-issue-link>
              <br />
            </template>
            <button
              class="linkify"
              on-click="openViewBlockedOn"
            >
              <i class="material-icons">list</i>
              View details
            </button>
          </div>
        </div>
      </template>

      <template is="dom-if" if="[[blocking]]">
        <div class="bottom-section-cell">
          <h3>Blocking:</h3>
          <div class="bottom-section-content">
            <template is="dom-repeat" items="[[blocking]]">
              <mr-issue-link
                project-name="[[projectName]]"
                issue="[[item]]"
              >
              </mr-issue-link>
              <br />
            </template>
          </div>
        </div>
      </template>

      <template is="dom-if" if="[[user]]">
        <div class="bottom-section-cell">
          <h3>Your Hotlists:</h3>
          <div class="bottom-section-content">
            <template is="dom-if" if="[[hotlistsByRole.user.length]]">
              <template
                is="dom-repeat"
                items="[[hotlistsByRole.user]]"
                as="hotlist"
              >
                <mr-hotlist-link hotlist="[[hotlist]]"></mr-hotlist-link>
              </template>
            </template>
            <button
              class="linkify"
              on-click="openUpdateHotlists"
            >
              <i class="material-icons">create</i> Update your hotlists
            </button>
          </div>
        </div>
      </template>

      <template is="dom-if" if="[[hotlistsByRole.participants.length]]">
        <div class="bottom-section-cell">
          <h3>Participant's Hotlists:</h3>
          <div class="bottom-section-content">
            <template
              is="dom-repeat"
              items="[[hotlistsByRole.participants]]"
              as="hotlist"
            >
              <mr-hotlist-link hotlist="[[hotlist]]"></mr-hotlist-link>
            </template>
          </div>
        </div>
      </template>

      <template is="dom-if" if="[[hotlistsByRole.others.length]]">
        <div class="bottom-section-cell">
          <h3>Other Hotlists:</h3>
          <div class="bottom-section-content">
            <template
              is="dom-repeat"
              items="[[hotlistsByRole.others]]"
              as="hotlist"
            >
              <mr-hotlist-link hotlist="[[hotlist]]"></mr-hotlist-link>
            </template>
          </div>
        </div>
      </template>
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
      user: Object,
      isStarred: {
        type: Boolean,
        value: false,
      },
      fetchingIsStarred: Boolean,
      starringIssue: Boolean,
      issueHotlists: Array,
      blocking: Array,
      sortedBlockedOn: Array,
      relatedIssues: Object,
      hotlistsByRole: {
        type: Object,
        computed: `_splitIssueHotlistsByRole(issueHotlists,
          user.userId, issue.ownerRef, issue.ccRefs)`,
      },
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
      user: user.user(state),
      projectName: state.projectName,
      projectConfig: project.project(state).config,
      isStarred: state.isStarred,
      fetchingIsStarred: state.requests.fetchIsStarred.requesting,
      starringIssue: state.requests.starIssue.requesting,
      blocking: issue.blockingIssues(state),
      sortedBlockedOn: issue.sortedBlockedOn(state),
      mergedInto: issue.mergedInto(state),
      relatedIssues: state.relatedIssues,
      issueHotlists: state.issueHotlists,
      _components: issue.components(state),
      _fieldDefs: issue.fieldDefs(state),
      _type: issue.type(state),
    };
  }

  toggleStar() {
    if (!this._canStar) return;

    const newIsStarred = !this.isStarred;
    const issueRef = {
      projectName: this.projectName,
      localId: this.issueId,
    };

    this.dispatchAction(actionCreator.starIssue(issueRef, newIsStarred));
  }

  openUpdateHotlists() {
    this.dispatchEvent(new CustomEvent('open-dialog', {
      bubbles: true,
      composed: true,
      detail: {
        dialogId: 'update-issue-hotlists',
      },
    }));
  }

  openViewBlockedOn(e) {
    this.dispatchEvent(new CustomEvent('open-dialog', {
      bubbles: true,
      composed: true,
      detail: {
        dialogId: 'reorder-related-issues',
      },
    }));
  }

  _computeCanStar(fetching, starring) {
    return !(fetching || starring);
  }

  _userIsParticipant(user, owner, cc) {
    if (owner && owner.userId === user.userId) {
      return true;
    }
    return cc && cc.some((ccUser) => ccUser && ccUser.UserId === user.userId);
  }

  _splitIssueHotlistsByRole(issueHotlists, userId, owner, cc) {
    const hotlists = {
      user: [],
      participants: [],
      others: [],
    };
    (issueHotlists || []).forEach((hotlist) => {
      if (hotlist.ownerRef.userId === userId) {
        hotlists.user.push(hotlist);
      } else if (this._userIsParticipant(hotlist.ownerRef, owner, cc)) {
        hotlists.participants.push(hotlist);
      } else {
        hotlists.others.push(hotlist);
      }
    });
    return hotlists;
  }

  // TODO(zhangtiff): Remove when upgrading to lit-element.
  _renderPluralS(count) {
    return count == 1 ? '' : 's';
  }

  // TODO(zhangtiff): Remove when upgrading to lit-element.
  _renderCount(count) {
    return count ? count : 0;
  }
}

customElements.define(MrIssueMetadata.is, MrIssueMetadata);
