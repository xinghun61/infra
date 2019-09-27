// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import page from 'page';
import qs from 'qs';
import {store, connectStore} from 'reducers/base.js';
import * as issue from 'reducers/issue.js';
import * as user from 'reducers/user.js';
import * as project from 'reducers/project.js';
import {prpcClient} from 'prpc-client-instance.js';
import {parseColSpec} from 'shared/issue-fields.js';
import {urlWithNewParams, userIsMember} from 'shared/helpers.js';
import 'elements/chops/chops-snackbar/chops-snackbar.js';
import 'elements/framework/mr-dropdown/mr-dropdown.js';
import 'elements/framework/mr-issue-list/mr-issue-list.js';
// eslint-disable-next-line max-len
import 'elements/issue-detail/dialogs/mr-update-issue-hotlists/mr-update-issue-hotlists.js';
import '../dialogs/mr-change-columns/mr-change-columns.js';
import '../mr-mode-selector/mr-mode-selector.js';

export const DEFAULT_ISSUES_PER_PAGE = 100;
const PARAMS_THAT_TRIGGER_REFRESH = ['q', 'can', 'sort', 'groupby', 'num',
  'start'];

export class MrListPage extends connectStore(LitElement) {
  static get styles() {
    return css`
      :host {
        display: block;
        box-sizing: border-box;
        width: 100%;
        padding: 0.5em 8px;
      }
      .container-loading,
      .container-no-issues {
        width: 100%;
        padding: 0 8px;
        font-size: var(--chops-main-font-size);
      }
      .container-no-issues {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
      }
      .container-no-issues p {
        margin: 0.5em;
      }
      .no-issues-block {
        display: block;
        padding: 1em 16px;
        margin-top: 1em;
        flex-grow: 1;
        width: 300px;
        max-width: 100%;
        text-align: center;
        background: var(--chops-blue-50);
        border-radius: 8px;
        border-bottom: var(--chops-normal-border);
      }
      .no-issues-block[hidden] {
        display: none;
      }
      .list-controls {
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
        padding: 0.5em 0;
      }
      .edit-actions {
        flex-grow: 0;
        box-sizing: border-box;
        display: flex;
        align-items: center;
      }
      .edit-actions button {
        height: 100%;
        background: none;
        display: flex;
        align-items: center;
        justify-content: center;
        border: none;
        border-right: var(--chops-normal-border);
        font-size: var(--chops-normal-font-size);
        cursor: pointer;
        transition: 0.2s background ease-in-out;
        color: var(--chops-link-color);
        line-height: 160%;
        padding: 0.25em 8px;
      }
      .edit-actions button:hover {
        background: var(--chops-blue-50);
      }
      .right-controls {
        flex-grow: 0;
        display: flex;
        align-items: center;
        justify-content: flex-end;
      }
      .next-link, .prev-link {
        display: inline-block;
        margin: 0 8px;
      }
      mr-mode-selector {
        margin-left: 8px;
      }
    `;
  }

  render() {
    const selectedRefs = this.selectedIssues.map(
        ({localId, projectName}) => ({localId, projectName}));
    return html`
      ${this._renderSnackbar()}
      ${this._renderControls()}
      ${this._renderListBody()}
      <mr-update-issue-hotlists
        .issueRefs=${selectedRefs}
      ></mr-update-issue-hotlists>
      <mr-change-columns
        .columns=${this.columns}
        .queryParams=${this.queryParams}
      ></mr-change-columns>
    `;
  }

  _renderSnackbar() {
    if (this.fetchingIssueList && this.totalIssues) {
      return html`
        <chops-snackbar>Updating issues...</chops-snackbar>
      `;
    }
    return '';
  }

  _renderListBody() {
    if (this.fetchingIssueList && !this.totalIssues) {
      return html`
        <div class="container-loading">
          Loading...
        </div>
      `;
    } else if (!this.totalIssues) {
      return html`
        <div class="container-no-issues">
          <p>
            The search query:
          </p>
          <strong>${this.queryParams.q}</strong>
          <p>
            did not generate any results.
          </p>
          <div class="no-issues-block">
            Type a new query in the search box above
          </div>
          <a
            href=${this._urlWithNewParams({can: 2, q: ''})}
            class="no-issues-block view-all-open"
          >
            View all open issues
          </a>
          <a
            href=${this._urlWithNewParams({can: 1})}
            class="no-issues-block consider-closed"
            ?hidden=${this.queryParams.can === '1'}
          >
            Consider closed issues
          </a>
        </div>
      `;
    }

    return html`
      <mr-issue-list
        .issues=${this.issues}
        .projectName=${this.projectName}
        .queryParams=${this.queryParams}
        .currentQuery=${this.currentQuery}
        .columns=${this.columns}
        .groups=${this.groups}
        ?selectionEnabled=${this.editingEnabled}
        ?starringEnabled=${this.starringEnabled}
        @selectionChange=${this._setSelectedIssues}
      ></mr-issue-list>
    `;
  }

  _renderControls() {
    const maxItems = this.maxItems;
    const startIndex = this.startIndex;
    const end = Math.min(startIndex + maxItems, this.totalIssues);
    const hasNext = end < this.totalIssues;
    const hasPrev = startIndex > 0;

    return html`
      <div class="list-controls">
        <div class="edit-actions">
          ${this.editingEnabled ? html`
            <button
              class="bulk-edit-button"
              @click=${this.bulkEdit}
            >
              Bulk edit
            </button>
            <button
              class="add-to-hotlist-button"
              @click=${this.addToHotlist}
            >
              Add to hotlist
            </button>
            <button
              class="change-columns-button"
              @click=${this.changeColumns}
            >
              Change columns
            </button>
            <mr-dropdown
              icon="more_vert"
              menuAlignment="left"
              label="More actions..."
              .items=${this._moreActions}
            ></mr-dropdown>
          ` : ''}
        </div>

        <div class="right-controls">
          ${hasPrev ? html`
            <a
              href=${this._urlWithNewParams({start: startIndex - maxItems})}
              class="prev-link"
            >
              &lsaquo; Prev
            </a>
          ` : ''}
          <div class="issue-count" ?hidden=${!this.totalIssues}>
            ${startIndex + 1} - ${end} of ${this.totalIssues}
          </div>
          ${hasNext ? html`
            <a
              href=${this._urlWithNewParams({start: startIndex + maxItems})}
              class="next-link"
            >
              Next &rsaquo;
            </a>
          ` : ''}
          <mr-mode-selector
            .projectName=${this.projectName}
            .queryParams=${this.queryParams}
            value="list"
          ></mr-mode-selector>
        </div>
      </div>
    `;
  }

  static get properties() {
    return {
      issues: {type: Array},
      totalIssues: {type: Number},
      queryParams: {type: Object},
      projectName: {type: String},
      fetchingIssueList: {type: Boolean},
      selectedIssues: {type: Array},
      columns: {type: Array},
      userDisplayName: {type: String},
      /**
       * The current search string the user is querying for.
       */
      currentQuery: {type: String},
      _isLoggedIn: {type: Boolean},
      _currentUser: {type: Object},
      _usersProjects: {type: Object},
    };
  };

  constructor() {
    super();
    this.issues = [];
    this.fetchingIssueList = false;
    this.selectedIssues = [];
    this.queryParams = {};
    this.columns = [];
    this._usersProjects = new Map();

    this._boundRefresh = this.refresh.bind(this);

    this._moreActions = [
      {
        text: 'Flag as spam',
        handler: () => this._flagIssues(true),
      },
      {
        text: 'Un-flag as spam',
        handler: () => this._flagIssues(false),
      },
    ];

    // Expose page.js for test stubbing.
    this.page = page;
  };

  connectedCallback() {
    super.connectedCallback();

    window.addEventListener('refreshList', this._boundRefresh);
  }

  disconnectedCallback() {
    super.disconnectedCallback();

    window.removeEventListener('refreshList', this._boundRefresh);
  }

  updated(changedProperties) {
    if (changedProperties.has('projectName')
        || changedProperties.has('currentQuery')) {
      this.refresh();
    } else if (changedProperties.has('queryParams')) {
      const oldParams = changedProperties.get('queryParams') || {};

      const shouldRefresh = PARAMS_THAT_TRIGGER_REFRESH.some((param) => {
        const oldValue = oldParams[param];
        const newValue = this.queryParams[param];
        return oldValue !== newValue;
      });

      if (shouldRefresh) {
        this.refresh();
      }
    }
    if (changedProperties.has('userDisplayName')) {
      store.dispatch(issue.fetchStarredIssues());
    }
  }

  refresh() {
    store.dispatch(issue.fetchIssueList(
        {...this.queryParams, q: this.currentQuery},
        this.projectName,
        {maxItems: this.maxItems, start: this.startIndex}));
  }

  stateChanged(state) {
    this._isLoggedIn = user.isLoggedIn(state);
    this._currentUser = user.user(state);
    this._usersProjects = user.projectsPerUser(state);

    this.issues = (issue.issueList(state) || []);
    this.totalIssues = (issue.totalIssues(state) || 0);
    this.fetchingIssueList = issue.requests(state).fetchIssueList.requesting;

    this.currentQuery = project.currentQuery(state);
    this.columns = project.currentColumns(state);
  }

  get starringEnabled() {
    return this._isLoggedIn;
  }

  get editingEnabled() {
    return this._isLoggedIn && (userIsMember(this._currentUser,
        this.projectName, this._usersProjects)
        || this._currentUser.isSiteAdmin);
  }

  get groups() {
    return parseColSpec(this.queryParams.groupby);
  }

  get maxItems() {
    return Number.parseInt(this.queryParams.num) || DEFAULT_ISSUES_PER_PAGE;
  }

  get startIndex() {
    const num = Number.parseInt(this.queryParams.start) || 0;
    return Math.max(0, num);
  }

  /**
   * Computes the current URL of the page with updated queryParams.
   *
   * @param {Object} newParams keys and values to override existing parameters.
   * @return {string} the new URL.
   */
  _urlWithNewParams(newParams) {
    // TODO(zhangtiff): replace list_new with list when switching over.
    const baseUrl = `/p/${this.projectName}/issues/list_new`;
    return urlWithNewParams(baseUrl, this.queryParams, newParams);
  }

  noneSelectedAlert(action) {
    // TODO(zhangtiff): Replace this with a modal for a more modern feel.
    alert(`Please select some issues to ${action}.`);
  }

  changeColumns() {
    this.shadowRoot.querySelector('mr-change-columns').open();
  }

  addToHotlist() {
    const issues = this.selectedIssues;
    if (!issues || !issues.length) {
      return this.noneSelectedAlert('add to hotlists');
    }
    this.shadowRoot.querySelector('mr-update-issue-hotlists').open();
  }

  bulkEdit() {
    const issues = this.selectedIssues;
    if (!issues || !issues.length) return this.noneSelectedAlert('edit');
    const params = {
      ids: issues.map((issue) => issue.localId).join(','),
      q: this.queryParams && this.queryParams.q,
    };
    this.page(`/p/${this.projectName}/issues/bulkedit?${qs.stringify(params)}`);
  }

  async _flagIssues(flagAsSpam = true) {
    const issues = this.selectedIssues;
    if (!issues || !issues.length) {
      return this.noneSelectedAlert(
          `${flagAsSpam ? 'flag' : 'un-flag'} as spam`);
    }
    const refs = issues.map((issue) => ({
      localId: issue.localId,
      projectName: issue.projectName,
    }));

    // TODO(zhangtiff): Refactor this into a shared action creator and
    // display the error on the frontend.
    try {
      await prpcClient.call('monorail.Issues', 'FlagIssues', {
        issueRefs: refs,
        flag: flagAsSpam,
      });
      this.refresh();
    } catch (e) {
      console.error(e);
    }
  }

  _setSelectedIssues() {
    const issueListRef = this.shadowRoot.querySelector('mr-issue-list');
    if (!issueListRef) return [];

    this.selectedIssues = issueListRef.selectedIssues;
  }
};
customElements.define('mr-list-page', MrListPage);
