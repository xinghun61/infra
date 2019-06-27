// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import qs from 'qs';

import '../mr-dropdown/mr-dropdown.js';
import '../mr-dropdown/mr-account-dropdown.js';
import './mr-search-bar.js';

import {SHARED_STYLES} from 'elements/shared/shared-styles.js';
import {prpcClient} from 'prpc-client-instance.js';

import ClientLogger from 'monitoring/client-logger';


/**
 * `<mr-header>`
 *
 * The header for Monorail.
 *
 */
export class MrHeader extends LitElement {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          color: var(--chops-header-text-color);
          box-sizing: border-box;
          background: hsl(221, 67%, 92%);
          width: 100%;
          height: var(--monorail-header-height);
          display: flex;
          flex-direction: row;
          justify-content: flex-start;
          align-items: center;
          z-index: 800;
          background-color: var(--chops-primary-header-bg);
          border-bottom: var(--chops-normal-border);
          top: 0;
          position: sticky;
          padding: 0 4px;
          font-size: var(--chops-large-font-size);
          margin-bottom: -1px;
        }
        @media (max-width: 840px) {
          :host {
            position: static;
          }
        }
        a {
          font-size: inherit;
          color: var(--chops-link-color);
          text-decoration: none;
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
          padding: 0 4px;
          flex-grow: 0;
          flex-shrink: 0;
        }
        a[hidden] {
          display: none;
        }
        a.button {
          font-size: inherit;
          height: auto;
          margin: 0 8px;
          border: 0;
          height: 30px;
        }
        mr-search-bar {
          margin-left: 8px;
          flex-grow: 2;
          max-width: 1000px;
        }
        i.material-icons {
          font-size: var(--chops-icon-font-size);
          color: var(--chops-primary-icon-color);
        }
        i.material-icons[hidden] {
          display: none;
        }
        .right-section {
          font-size: inherit;
          display: flex;
          align-items: center;
          height: 100%;
          margin-left: auto;
          justify-content: flex-end;
        }
      `,
    ];
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <a href=${this.projectName ? `/p/${this.projectName}/` : '/'}>
        ${this.projectThumbnailUrl ? html`
          <img
            class="project-logo"
            src=${this.projectThumbnailUrl}
            title="Issues"
          />
        ` : ''}
        <i
          class="material-icons"
          title="Issues"
          ?hidden=${this.projectThumbnailUrl}
        >home</i>
      </a>
      <mr-dropdown
        class="project-selector"
        .text=${this.projectName || 'Select a project'}
        .items=${this._projectDropdownItems}
        menuAlignment="left"
        title=${this.presentationConfig.projectSummary}
      ></mr-dropdown>
      <a
        ?hidden=${!this.projectName}
        class="button emphasized new-issue-link"
        href=${this.issueEntryUrl}
      >
        New issue
      </a>
      <mr-search-bar
        .projectName=${this.projectName}
        .userDisplayName=${this.userDisplayName}
        .projectSavedQueries=${this.presentationConfig.savedQueries}
        .defaultCan=${this._defaultCan}
        .initialValue=${this._initialSearch}
        .queryParams=${this.queryParams}
        ?hidden=${!this.projectName}
      ></mr-search-bar>

      <div class="right-section">
        <mr-dropdown
          icon="settings"
          .items=${this._projectSettingsItems}
          ?hidden=${!this.projectName}
        ></mr-dropdown>

        ${this.userDisplayName ? html`
          <mr-account-dropdown
            .userDisplayName=${this.userDisplayName}
            .logoutUrl=${this.logoutUrl}
            .loginUrl=${this.loginUrl}
          ></mr-account-dropdown>
        `: ''}
        <a
          href=${this.loginUrl}
          ?hidden=${this.userDisplayName}
        >Sign in</a>
      </div>
    `;
  }

  static get properties() {
    return {
      canAdministerProject: {type: Boolean},
      loginUrl: {type: String},
      logoutUrl: {type: String},
      projectName: {type: String},
      // Project thumbnail is set separately from presentationConfig to prevent
      // "flashing" logo when navigating EZT pages.
      projectThumbnailUrl: {type: String},
      userDisplayName: {type: String},
      userProjects: {type: Object},
      presentationConfig: {type: Object},
      queryParams: {type: Object},
      // TODO(zhangtiff): Change this to be dynamically computed by the
      //   frontend with logic similar to ComputeIssueEntryURL().
      issueEntryUrl: {type: String},
      clientLogger: {type: Object},
    };
  }

  constructor() {
    super();

    // TODO(zhangtiff): Make this use permissions from API.
    this.canAdministerProject = true;

    this.presentationConfig = {};
    this.clientLogger = new ClientLogger('mr-header');
  }

  connectedCallback() {
    super.connectedCallback();

    // Remove question mark at the start.
    const queryString = window.location.search.substring(1);

    // TODO(zhangtiff): Replace this with page.js integration.
    // Note: Until we add page.js integration, this does not handle
    // frontend route changes.
    this.queryParams = qs.parse(queryString);
  }

  updated(changedProperties) {
    if (changedProperties.has('projectName')) {
      this._fetchPresentationConfig(this.projectName);
    }
    if (changedProperties.has('userDisplayName')) {
      this._fetchUserProjects(this.userDisplayName);
    }
  }

  // TODO(zhangtiff): Make this into an action creator.
  async _fetchPresentationConfig(projectName) {
    const presentationConfig = await prpcClient.call(
      'monorail.Projects', 'GetPresentationConfig', {projectName});

    this.presentationConfig = presentationConfig;
    this.projectThumbnailUrl = presentationConfig.projectThumbnailUrl;
  }

  async _fetchUserProjects(displayName) {
    // Only fetch projects for logged in users.
    if (!displayName) return;
    // TODO(zhangtiff): Add this state to Redux. This is left out from
    //   Redux for now because this code is meant to run on non-SPA pages
    //   as well.
    const userRefs = [{displayName}];
    const response = await prpcClient.call(
      'monorail.Users', 'GetUsersProjects', {userRefs});
    this.userProjects = response.usersProjects[0];
  }

  get _projectDropdownItems() {
    const {userProjects, loginUrl} = this;
    if (!userProjects) {
      return [{text: 'Sign in to see your projects', url: loginUrl}];
    }
    const items = [];
    const starredProjects = userProjects.starredProjects || [];
    const projects = (userProjects.ownerOf || [])
      .concat(userProjects.memberOf || [])
      .concat(userProjects.contributorTo || []);

    if (projects.length) {
      projects.sort();
      items.push({text: 'My Projects', separator: true});

      projects.forEach((project) => {
        items.push({text: project, url: `/p/${project}/`});
      });
    }

    if (starredProjects.length) {
      starredProjects.sort();
      items.push({text: 'Starred Projects', separator: true});

      starredProjects.forEach((project) => {
        items.push({text: project, url: `/p/${project}/`});
      });
    }

    if (items.length) {
      items.push({separator: true});
    }

    items.push({text: 'All projects', url: '/hosting/'});
    items.forEach((item) => {
      item.handler = () => this._projectChangedHandler(item);
    });
    return items;
  }

  get _projectSettingsItems() {
    const {projectName, canAdministerProject} = this;
    const items = [
      {text: 'People', url: `/p/${projectName}/people/list`},
      {text: 'Development Process', url: `/p/${projectName}/adminIntro`},
      {text: 'History', url: `/p/${projectName}/updates/list`},
    ];

    if (canAdministerProject) {
      items.push({separator: true});
      items.push({text: 'Administer', url: `/p/${projectName}/admin`});
    }
    return items;
  }

  get _initialSearch() {
    const defaultQuery = this.presentationConfig
      && this.presentationConfig.defaultQuery;
    const q = this.queryParams && this.queryParams.q;
    const qIsString = typeof q === 'string';
    return qIsString ? q : defaultQuery;
  }

  get _defaultCan() {
    const can = this.queryParams && this.queryParams.can;
    return can ? can : '2';
  }

  _projectChangedHandler(item) {
    // Just log it to GA and continue.
    this.clientLogger.logEvent('project-change', item.url);
  }
}

customElements.define('mr-header', MrHeader);
