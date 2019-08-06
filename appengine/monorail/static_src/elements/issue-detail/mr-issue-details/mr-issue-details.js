// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import * as ui from 'elements/reducers/ui.js';
import 'elements/framework/mr-comment-content/mr-description.js';
import '../mr-comment-list/mr-comment-list.js';
import '../metadata/mr-edit-metadata/mr-edit-issue.js';
import {commentListToDescriptionList} from 'elements/shared/converters.js';

/**
 * `<mr-issue-details>`
 *
 * This is the main details section for a given issue.
 *
 */
export class MrIssueDetails extends connectStore(LitElement) {
  static get styles() {
    return css`
      :host {
        font-size: var(--chops-main-font-size);
        background-color: white;
        padding: 0;
        padding-bottom: 1em;
        display: flex;
        align-items: stretch;
        justify-content: flex-start;
        flex-direction: column;
        z-index: 1;
        margin: 0;
        box-sizing: border-box;
      }
      h3 {
        margin-top: 1em;
      }
      mr-description {
        margin-bottom: 1em;
      }
    `;
  }

  render() {
    let comments = [];
    let descriptions = [];

    if (this.commentsByApproval && this.commentsByApproval.has('')) {
      // Comments without an approval go into the main view.
      const mainComments = this.commentsByApproval.get('');
      comments = mainComments.slice(1);
      descriptions = commentListToDescriptionList(mainComments);
    }

    return html`
      <mr-description .descriptionList=${descriptions}></mr-description>
      <mr-comment-list
        headingLevel="2"
        .comments=${comments}
        .commentsShownCount=${this.commentsShownCount}
      >
        <mr-edit-issue></mr-edit-issue>
      </mr-comment-list>
    `;
  }

  static get properties() {
    return {
      commentsByApproval: {type: Object},
      commentsShownCount: {type: Number},
    };
  }

  constructor() {
    super();
    this.commentsByApproval = new Map();
  }

  stateChanged(state) {
    this.commentsByApproval = issue.commentsByApprovalName(state);
  }

  updated(changedProperties) {
    super.updated(changedProperties);
    this._measureCommentLoadTime(changedProperties);
  }

  async _measureCommentLoadTime(changedProperties) {
    if (!changedProperties.has('commentsByApproval')) {
      return;
    }
    if (!this.commentsByApproval || this.commentsByApproval.size === 0) {
      // For cold loads, if the GetIssue call returns before ListComments,
      // commentsByApproval is initially set to an empty Map. Filter that out.
      return;
    }
    const fullAppLoad = ui.navigationCount(store.getState()) === 1;
    if (!(fullAppLoad || changedProperties.get('commentsByApproval'))) {
      // For hot loads, the previous issue data is still in the Redux store, so
      // the first update sets the comments to the previous issue's comments.
      // We need to wait for the following update.
      return;
    }
    const startMark = fullAppLoad ? undefined : 'start load issue detail page';
    if (startMark && !performance.getEntriesByName(startMark).length) {
      // Modifying the issue template, description, comments, or attachments
      // triggers a comment update. We only want to include full issue loads.
      return;
    }

    await Promise.all(_subtreeUpdateComplete(this));

    const endMark = 'finish load issue detail comments';
    performance.mark(endMark);

    const measurementType = fullAppLoad ? 'from outside app' : 'within app';
    const measurementName = `load issue detail page (${measurementType})`;
    performance.measure(measurementName, startMark, endMark);

    const measurement =
      performance.getEntriesByName(measurementName)[0].duration;
    window.getTSMonClient().recordIssueCommentsLoadTiming(
      measurement, fullAppLoad);

    // Be sure to clear this mark even on full page navigations.
    performance.clearMarks('start load issue detail page');
    performance.clearMarks(endMark);
    performance.clearMeasures(measurementName);
  }
}

/**
 * Recursively traverses all shadow DOMs in an element subtree and returns an
 * Array containing the updateComplete Promises for all lit-element nodes.
 * @param {!LitElement} element
 * @return {!Array<Promise<Boolean>>}
 */
function _subtreeUpdateComplete(element) {
  if (!(element.shadowRoot && element.updateComplete)) {
    return [];
  }

  const children = element.shadowRoot.querySelectorAll('*');
  const childPromises = Array.from(children, (e) => _subtreeUpdateComplete(e));
  return [element.updateComplete].concat(...childPromises);
}

customElements.define('mr-issue-details', MrIssueDetails);
