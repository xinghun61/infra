// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import * as project from 'elements/reducers/project.js';
import * as user from 'elements/reducers/user.js';
import 'elements/framework/links/mr-user-link/mr-user-link.js';
import 'elements/framework/links/mr-hotlist-link/mr-hotlist-link.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles.js';
import {pluralize} from 'elements/shared/helpers.js';
import './mr-metadata.js';


/**
 * `<mr-issue-metadata>`
 *
 * The metadata view for a single issue. Contains information such as the owner.
 *
 */
export class MrIssueMetadata extends connectStore(LitElement) {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          box-sizing: border-box;
          padding: 0.25em 8px;
          max-width: 100%;
          display: block;
        }
        h3 {
          display: block;
          font-size: var(--chops-main-font-size);
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
          font-size: var(--chops-icon-font-size);
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
      `,
    ];
  }

  render() {
    const hotlistsByRole = this._hotlistsByRole;
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <div class="star-line">
        <button class="star-button" @click=${this.toggleStar} ?disabled=${!this._canStar}>
          ${this.isStarred ? html`
            <i class="material-icons starred" title="You've starred this issue">
              star
            </i>
          `: html`
            <i
              class="material-icons"
              title="${this._userId ? 'Click' : 'Log in'} to star this issue"
            >
              star_border
            </i>
          `}
        </button>
        Starred by ${this.issue.starCount || 0} ${pluralize(this.issue.starCount, 'user')}
      </div>
      <mr-metadata
        aria-label="Issue Metadata"
        .owner=${this.issue.ownerRef}
        .cc=${this.issue.ccRefs}
        .issueStatus=${this.issue.statusRef}
        .components=${this._components}
        .fieldDefs=${this._fieldDefs}
        .mergedInto=${this.mergedInto}
        .modifiedTimestamp=${this.issue.modifiedTimestamp}
      ></mr-metadata>

      <div class="labels-container">
        ${this.issue.labelRefs && this.issue.labelRefs.map((label) => html`
          <a
            title="${_labelTitle(this.labelDefMap, label)}"
            href="/p/${this.issueRef.projectName}/issues/list?q=label:${label.label}"
            class="label"
            ?data-derived=${label.isDerived}
          >${label.label}</a>
          <br>
        `)}
      </div>

      ${this.sortedBlockedOn.length ? html`
        <div class="bottom-section-cell">
          <h3>BlockedOn:</h3>
            <div class="bottom-section-content">
            ${this.sortedBlockedOn.map((issue) => html`
              <mr-issue-link
                .projectName=${this.issueRef.projectName}
                .issue=${issue}
              >
              </mr-issue-link>
              <br />
            `)}
            <button
              class="linkify"
              @click=${this.openViewBlockedOn}
            >
              <i class="material-icons">list</i>
              View details
            </button>
          </div>
        </div>
      `: ''}

      ${this.blocking.length ? html`
        <div class="bottom-section-cell">
          <h3>Blocking:</h3>
          <div class="bottom-section-content">
            ${this.blocking.map((issue) => html`
              <mr-issue-link
                .projectName=${this.issueRef.projectName}
                .issue=${issue}
              >
              </mr-issue-link>
              <br />
            `)}
          </div>
        </div>
      `: ''}

      ${this._userId ? html`
        <div class="bottom-section-cell">
          <h3>Your Hotlists:</h3>
          <div class="bottom-section-content" id="user-hotlists">
            ${this._renderHotlists(hotlistsByRole.user)}
            <button
              class="linkify"
              @click=${this.openUpdateHotlists}
            >
              <i class="material-icons">create</i> Update your hotlists
            </button>
          </div>
        </div>
      `: ''}

      ${hotlistsByRole.participants.length ? html`
        <div class="bottom-section-cell">
          <h3>Participant's Hotlists:</h3>
          <div class="bottom-section-content">
            ${this._renderHotlists(hotlistsByRole.participants)}
          </div>
        </div>
      ` : ''}

      ${hotlistsByRole.others.length ? html`
        <div class="bottom-section-cell">
          <h3>Other Hotlists:</h3>
          <div class="bottom-section-content">
            ${this._renderHotlists(hotlistsByRole.others)}
          </div>
        </div>
      ` : ''}
    `;
  }

  _renderHotlists(hotlists) {
    return hotlists.map((hotlist) => html`
      <mr-hotlist-link .hotlist=${hotlist}></mr-hotlist-link>
    `);
  }

  static get properties() {
    return {
      issue: {type: Object},
      issueRef: {type: Object},
      projectConfig: String,
      user: {type: Object},
      isStarred: {type: Boolean},
      fetchingIsStarred: {type: Boolean},
      starringIssue: {type: Boolean},
      issueHotlists: {type: Array},
      blocking: {type: Array},
      sortedBlockedOn: {type: Array},
      relatedIssues: {type: Object},
      labelDefMap: {type: Object},
      _components: {type: Array},
      _fieldDefs: {type: Array},
      _type: {type: String},
    };
  }

  stateChanged(state) {
    this.issue = issue.issue(state);
    this.issueRef = issue.issueRef(state);
    this.user = user.user(state);
    this.projectConfig = project.project(state).config;
    this.isStarred = issue.isStarred(state);
    this.fetchingIsStarred = issue.requests(state).fetchIsStarred.requesting;
    this.starringIssue = issue.requests(state).star.requesting;
    this.blocking = issue.blockingIssues(state);
    this.sortedBlockedOn = issue.sortedBlockedOn(state);
    this.mergedInto = issue.mergedInto(state);
    this.relatedIssues = issue.relatedIssues(state);
    this.issueHotlists = issue.hotlists(state);
    this.labelDefMap = project.labelDefMap(state);
    this._components = issue.components(state);
    this._fieldDefs = issue.fieldDefs(state);
    this._type = issue.type(state);
  }

  get _userId() {
    return this.user && this.user.userId;
  }

  get _canStar() {
    const {fetchingIsStarred, starringIssue, _userId} = this;
    return _userId && !fetchingIsStarred && !starringIssue;
  }

  get _hotlistsByRole() {
    const issueHotlists = this.issueHotlists;
    const owner = this.issue && this.issue.ownerRef;
    const cc = this.issue && this.issue.ccRefs;

    const hotlists = {
      user: [],
      participants: [],
      others: [],
    };
    (issueHotlists || []).forEach((hotlist) => {
      if (hotlist.ownerRef.userId === this._userId) {
        hotlists.user.push(hotlist);
      } else if (_userIsParticipant(hotlist.ownerRef, owner, cc)) {
        hotlists.participants.push(hotlist);
      } else {
        hotlists.others.push(hotlist);
      }
    });
    return hotlists;
  }

  toggleStar() {
    if (!this._canStar) return;

    const newIsStarred = !this.isStarred;
    const issueRef = this.issueRef;

    store.dispatch(issue.star(issueRef, newIsStarred));
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
}

function _userIsParticipant(user, owner, cc) {
  if (owner && owner.userId === user.userId) {
    return true;
  }
  return cc && cc.some((ccUser) => ccUser && ccUser.UserId === user.userId);
}

function _labelTitle(labelDefMap, label) {
  if (!label) return '';
  let docstring = '';
  const key = label.label.toLowerCase();
  if (labelDefMap && labelDefMap.has(key)) {
    docstring = labelDefMap.get(key).docstring;
  }
  return (label.isDerived ? 'Derived: ' : '') + label.label
    + (docstring ? ` = ${docstring}` : '');
}

customElements.define('mr-issue-metadata', MrIssueMetadata);
