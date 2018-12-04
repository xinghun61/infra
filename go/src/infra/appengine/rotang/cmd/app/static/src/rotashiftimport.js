import {LitElement, html} from '@polymer/lit-element';
import {DateTime} from 'luxon';
import * as constants from './constants';

class RotaShiftImport extends LitElement {
  static get properties() {
    return {
      rota: {},
      shifts: {},
      importStatus: {},
    };
  }

  async getJSON() {
    try {
      const res = await fetch(encodeURI(`/importshiftsjson?name=${this.rota}`));
      if (!res.ok) {
        throw res;
      }
      this.shifts = await res.json();
      this.importStatus = html`<small class="ok">(ok)</small>`;
    } catch (err) {
      this.importStatus = html`<small class="fail">${err.text()}</small>`;
    }
  }

  async storeShifts() {
    try {
      const res = await fetch(encodeURI(`/importshiftsjson?name=${this.rota}&store=true`));
      if (!res.ok) {
        throw res;
      }
      this.importStatus = html`<small class="ok">Shifts imported</small>`;
      this.shifts = null;
    } catch (err) {
      this.importStatus = html`<small class="fail">${err.text()}</small>`;
    }
  }

  generateShifts() {
    if (!this.shifts) {
      return;
    }
    return html`
      <table id="shifts">
      <thead>
        <tr>
          <th>Name</th>
          <th>Oncallers</th>
          <th>Start</th>
          <th>End</th>
         </tr>
      </thead>
      <tbody>
      ${this.shifts.map((s) =>html`
        <tr>
          <td>${s.Name}</td>
          <td>${this.generateOncallers(s)}</td>
          <td>${DateTime.fromISO(s.StartTime).setZone(constants.zone)
            .toFormat(constants.timeFormat)}</td>
          <td>${DateTime.fromISO(s.EndTime).setZone(constants.zone)
            .toFormat(constants.timeFormat)}</td>
        </tr>
      `)}
      </tbody>
      </table>
    `;
  }

  generateOncallers(shift) {
    if (!shift.OnCall) {
      return;
    }
    return html`
    <div class="flex-container">
      ${shift.OnCall.map((o) => html`
        <div>${o.Email}</div>
      `)}
    </div>
    `;
  }

  generateButton() {
    if (!this.shifts) {
      return html`
        <button type="button" @click=${() => this.getJSON()}>
          Import Shifts
        </button>
      `;
    }
    return html`
      <button type="button" @click=${() => this.storeShifts()}>
        Submit Shifts
      </button>
    `;
  }

  render() {
    return html`
    <style>
    .ok {
      color: green;
      background-color: transparent;
    }

    .fail {
      color: red;
      background-color: transparent;
    }
    #shifts {
      font-size: small;
      border-collapse: collapse;
    }

    #shifts td, #shifts th {
      border: 1px, solid #ddd;
      padding: 8px;
    }

    #shifts th {
      text-align: left;
    }

    #shifts tr:nth-child(even){background-color: #f2f2f2;}
    #oncallers tr {
      all: initial !important;
    };

    .flex-container {
      display: flex;
    }
    </style>
    ${this.generateShifts()}
    ${this.generateButton()}
    ${this.importStatus && this.importStatus}
    `;
  };
}

customElements.define('rota-shiftimport', RotaShiftImport);
