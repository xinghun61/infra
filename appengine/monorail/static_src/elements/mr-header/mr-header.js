// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import qs from 'qs';

import '../mr-dropdown/mr-dropdown.js';
import '../mr-dropdown/mr-account-dropdown.js';
import './mr-search-bar.js';

// TODO(zhangtiff): Move these styles outside of FLT folder.
import '../flt/shared/mr-flt-styles.js';
import {prpcClient} from '../../prpc-client-instance.js';

import ClientLogger from '../../monitoring/client-logger';

/**
 * `<mr-header>`
 *
 * The header for Monorail.
 *
 */
export class MrHeader extends PolymerElement {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style include="mr-flt-styles">
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
          font-size: 14px;
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
          height: 26px;
        }
        mr-search-bar {
          margin-left: 8px;
          flex-grow: 2;
          max-width: 1000px;
        }
        i.material-icons {
          font-size: 20px;
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
      </style>
      <a href\$="/p/[[projectName]]/">
        <template is="dom-if" if="[[projectThumbnailUrl]]">
          <img
            class="project-logo"
            src$="[[projectThumbnailUrl]]"
            title="Issues"
          />
        </template>
        <i
          class="material-icons"
          title="Issues"
          hidden\$="[[projectThumbnailUrl]]"
        >home</i>
      </a>
      <mr-dropdown
        class="project-selector"
        text="[[projectName]]"
        items="[[_projectDropdownItems]]"
        menu-alignment="left"
        title$="[[presentationConfig.projectSummary]]"
      ></mr-dropdown>
      <a class="button emphasized new-issue-link" href\$="[[issueEntryUrl]]">
        New issue
      </a>
      <mr-search-bar
        project-name="[[projectName]]"
        user-display-name="[[userDisplayName]]"
        project-saved-queries="[[presentationConfig.savedQueries]]"
        default-can="[[_computeDefaultCan(queryParams.can)]]"
        initial-value="[[_computeInitialSearch(
          presentationConfig.defaultQuery, queryParams.q)]]"
        query-params="[[queryParams]]"
      ></mr-search-bar>

      <div class="right-section">
        <mr-dropdown
          icon="settings"
          items="[[_projectSettingsItems]]"
        ></mr-dropdown>

        <template is="dom-if" if="[[userDisplayName]]">
          <mr-account-dropdown
            user-display-name="[[userDisplayName]]"
            logout-url="[[logoutUrl]]"
            login-url="[[loginUrl]]"
          ></mr-account-dropdown>
        </template>
        <a
          href\$="[[loginUrl]]"
          hidden\$="[[userDisplayName]]"
        >Sign in</a>
      </div>
    `;
  }

  static get is() {
    return 'mr-header';
  }

  static get properties() {
    return {
      // TODO(zhangtiff): Make this use permissions from API.
      canAdministerProject: {
        type: Boolean,
        value: true,
      },
      loginUrl: String,
      logoutUrl: String,
      projectName: {
        type: String,
        observer: '_projectChanged',
      },
      projectThumbnailUrl: String,
      userDisplayName: {
        type: String,
        observer: '_userChanged',
      },
      userProjects: Object,
      presentationConfig: Object,
      queryParams: Object,
      // TODO(zhangtiff): Change this to be dynamically computed by the
      //   frontend with logic similar to ComputeIssueEntryURL().
      issueEntryUrl: String,
      _projectSettingsItems: {
        type: Array,
        computed: '_computeProjectSettingsItems(projectName, canAdministerProject)',
      },
      _projectDropdownItems: {
        type: Array,
        computed: '_computeProjectDropdownItems(userProjects, loginUrl)',
      },
    };
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

  ready() {
    super.ready();
    this.clientLogger = new ClientLogger('mr-header');
  }

  _projectChanged(projectName) {
    const presentationConfigPromise = prpcClient.call(
      'monorail.Projects', 'GetPresentationConfig', {projectName});
    presentationConfigPromise.then((presentationConfig) => {
      this.presentationConfig = presentationConfig;
      this.projectThumbnailUrl = presentationConfig.projectThumbnailUrl;
    });
  }

  _userChanged(displayName) {
    if (!displayName) return;
    // Only fetch projects for logged in users.
    // TODO(zhangtiff): Add this state to Redux. This is left out from
    //   Redux for now because this code is meant to run on non-SPA pages
    //   as well.
    const userProjectsPromise = prpcClient.call(
      'monorail.Projects', 'GetUserProjects', {});
    userProjectsPromise.then((userProjects) => {
      this.userProjects = userProjects;
    });
  }

  _computeProjectDropdownItems(userProjects, loginUrl) {
    if (!userProjects) {
      return [{text: 'Sign in to see your projects', url: loginUrl}];
    }
    let items = [];
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

  _projectChangedHandler(item) {
    // Just log it to GA and continue.
    this.clientLogger.logEvent('project-change', item.url);
  }

  _computeProjectSettingsItems(projectName, canAdministerProject) {
    let items = [
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

  _computeInitialSearch(defaultQuery, q) {
    const qIsString = typeof q === 'string';
    return qIsString ? q : defaultQuery;
  }

  _computeDefaultCan(can) {
    return can ? can : 2;
  }
}

customElements.define(MrHeader.is, MrHeader);
