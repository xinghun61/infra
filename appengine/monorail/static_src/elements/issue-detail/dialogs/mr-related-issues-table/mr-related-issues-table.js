// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import 'elements/chops/chops-dialog/chops-dialog.js';
import 'elements/framework/links/mr-issue-link/mr-issue-link.js';
import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles.js';
import {ISSUE_EDIT_PERMISSION} from 'elements/shared/permissions';
import {prpcClient} from 'prpc-client-instance.js';

export class MrRelatedIssuesTable extends connectStore(LitElement) {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          display: block;
          font-size: var(--chops-main-font-size);
        }
        table {
          word-wrap: break-word;
          width: 100%;
        }
        tr {
          font-weight: normal;
          text-align: left;
          margin: 0 auto;
          padding: 2em 1em;
          height: 20px;
        }
        td {
          background: #f8f8f8;
          padding: 4px;
          padding-left: 8px;
          text-overflow: ellipsis;
        }
        th {
          text-decoration: none;
          margin-right: 0;
          padding-right: 0;
          padding-left: 8px;
          white-space: nowrap;
          background: #e3e9ff;
          text-align: left;
          border-right: 1px solid #fff;
          border-top: 1px solid #fff;
        }
        tr.dragged td {
          background: #eee;
        }
        h3.medium-heading {
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
        }
        button {
          background: none;
          border: none;
          color: inherit;
          cursor: pointer;
          margin: 0;
          padding: 0;
        }
        i.material-icons {
          font-size: var(--chops-icon-font-size);
          color: var(--chops-primary-icon-color);
        }
        .draggable {
          cursor: grab;
        }
        .error {
          max-width: 100%;
          color: red;
          margin-bottom: 1em;
        }
      `,
    ];
  }

  render() {
    const rerankEnabled = (this.issuePermissions
      || []).includes(ISSUE_EDIT_PERMISSION);
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <chops-dialog>
        <h3 class="medium-heading">
          <span>Blocked on issues</span>
          <button aria-label="close" @click=${this.close}>
            <i class="material-icons">close</i>
          </button>
        </h3>
        ${this.error ? html`
          <div class="error">${this.error}</div>
        ` : ''}
        <table><tbody>
          <tr>
            ${rerankEnabled ? html`<th></th>` : ''}
            ${this.columns.map((column) => html`
              <th>${column}</th>
            `)}
          </tr>

          ${this._renderedRows.map((row, index) => html`
            <tr
              class=${index === this.srcIndex ? 'dragged' : ''}
              draggable=${rerankEnabled && row.draggable}
              data-index=${index}
              @dragstart=${this._dragstart}
              @dragend=${this._dragend}
              @dragover=${this._dragover}
              @drop=${this._dragdrop}
            >
              ${rerankEnabled ? html`
                <td>
                  ${rerankEnabled && row.draggable ? html`
                    <i class="material-icons draggable">drag_indicator</i>
                  ` : ''}
                </td>
              ` : ''}

              ${row.cells.map((cell) => html`
                <td>
                  ${cell.type === 'issue' ? html`
                    <mr-issue-link
                      .projectName=${this.issueRef.projectName}
                      .issue=${cell.issue}
                    ></mr-issue-link>
                  ` : ''}
                  ${cell.type === 'text' ? cell.content : ''}
                </td>
              `)}
            </tr>
          `)}
        </tbody></table>
      </chops-dialog>
    `;
  }

  static get properties() {
    return {
      columns: {type: Array},
      error: {type: String},
      srcIndex: {type: Number},
      issueRef: {type: Object},
      issuePermissions: {type: Array},
      sortedBlockedOn: {type: Array},
      _renderedRows: {type: Array},
    };
  }

  stateChanged(state) {
    this.issueRef = issue.issueRef(state);
    this.issuePermissions = issue.permissions(state);
    this.sortedBlockedOn = issue.sortedBlockedOn(state);
  }

  constructor() {
    super();
    this.columns = ['Issue', 'Summary'];
  }

  update(changedProperties) {
    if (changedProperties.has('sortedBlockedOn')) {
      this.reset();
    }
    super.update(changedProperties);
  }

  get _rows() {
    const blockedOn = this.sortedBlockedOn;
    if (!blockedOn) return [];
    return blockedOn.map((issue) => {
      const isClosed = issue.statusRef ? !issue.statusRef.meansOpen : false;
      const row = {
        draggable: !isClosed,
        cells: [
          {
            type: 'issue',
            issue: issue,
            isClosed: Boolean(isClosed),
          },
          {
            type: 'text',
            content: issue.summary,
          },
        ],
      };
      return row;
    });
  }

  async open() {
    await this.updateComplete;
    this.reset();
    this.shadowRoot.querySelector('chops-dialog').open();
  }

  close() {
    this.shadowRoot.querySelector('chops-dialog').close();
  }

  reset() {
    this.error = null;
    this.srcIndex = null;
    this._renderedRows = this._rows.slice();
  }

  _dragstart(e) {
    if (e.currentTarget.draggable) {
      this.srcIndex = Number(e.currentTarget.dataset.index);
      e.dataTransfer.setDragImage(new Image(), 0, 0);
    }
  }

  _dragover(e) {
    if (e.currentTarget.draggable && this.srcIndex !== null) {
      e.preventDefault();
      const targetIndex = Number(e.currentTarget.dataset.index);
      this._reorderRows(this.srcIndex, targetIndex);
      this.srcIndex = targetIndex;
    }
  }

  _dragend(e) {
    if (this.srcIndex !== null) {
      this.reset();
    }
  }

  _dragdrop(e) {
    if (e.currentTarget.draggable && this.srcIndex !== null) {
      const src = this._renderedRows[this.srcIndex];
      if (this.srcIndex > 0) {
        const target = this._renderedRows[this.srcIndex - 1];
        const above = false;
        this._reorderBlockedOn(src, target, above);
      } else if (this.srcIndex === 0 &&
                 this._renderedRows[1] && this._renderedRows[1].draggable) {
        const target = this._renderedRows[1];
        const above = true;
        this._reorderBlockedOn(src, target, above);
      }
      this.srcIndex = null;
    }
  }

  _reorderBlockedOn(srcArg, targetArg, above) {
    const src = srcArg.cells[0].issue;
    const target = targetArg.cells[0].issue;

    const reorderRequest = prpcClient.call(
      'monorail.Issues', 'RerankBlockedOnIssues', {
        issueRef: this.issueRef,
        movedRef: {
          projectName: src.projectName,
          localId: src.localId,
        },
        targetRef: {
          projectName: target.projectName,
          localId: target.localId,
        },
        splitAbove: above,
      });

    reorderRequest.then((response) => {
      store.dispatch(issue.fetch({
        issueRef: this.issueRef,
      }));
    }, (error) => {
      this.reset();
      this.error = error.description;
    });
  }

  _reorderRows(srcIndex, toIndex) {
    if (srcIndex <= toIndex) {
      this._renderedRows = this._renderedRows.slice(0, srcIndex).concat(
        this._renderedRows.slice(srcIndex + 1, toIndex + 1),
        [this._renderedRows[srcIndex]],
        this._renderedRows.slice(toIndex + 1));
    } else {
      this._renderedRows = this._renderedRows.slice(0, toIndex).concat(
        [this._renderedRows[srcIndex]],
        this._renderedRows.slice(toIndex, srcIndex),
        this._renderedRows.slice(srcIndex + 1));
    }
  }
}

customElements.define('mr-related-issues-table', MrRelatedIssuesTable);
