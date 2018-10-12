import {LitElement, html} from '@polymer/lit-element';
import {DateTime} from 'luxon';
import * as constants from './constants';

class RotaShiftHistory extends LitElement {
  static get properties() {
    return {
      shifts: {type: constants.Shifts},
      hide: {},
    };
  }

  constructor() {
    super();
    this.datesFixed = false;
    this.hide = true;
  }


  toDateTime(ss) {
    for (let split of ss) {
      for (let shift of split.Shifts) {
        shift.StartTime = DateTime.fromISO(shift.StartTime.toString())
          .setZone(constants.zone);
        shift.EndTime = DateTime.fromISO(shift.EndTime.toString())
          .setZone(constants.zone);
      }
    }
  }

  onCallers(shift) {
    if (!shift.OnCall) {
      return;
    }
    return shift.OnCall.map((oncall, oncallIdx) => html`
             <td>${oncall.Email}</td>`);
  }

  shiftsTemplate(ss) {
    return ss.Shifts.map((i, shiftIdx) => html`
    <tr>
      <td>
      <table>
      <tbody>
        ${this.onCallers(i)}
      </tbody>
      </table>
      </td>
      <td>${i.StartTime.toFormat(constants.timeFormat)}</td>
      <td>${i.EndTime.toFormat(constants.timeFormat)}</td>
      <td>${i.Comment}</td>
    </tr>`);
  }

  historyShifts() {
    if (this.hide) {
      return html`
        <button type="button" @click=${() =>(this.hide = false)}>Show History
        </button>`;
    }
    if (!this.shifts || !this.shifts.SplitShifts) {
      return;
    }

    return html`<legend>Previous shifts</legend>
      ${this.shifts.SplitShifts.map((s, splitIdx) => html`
        <h4>${s.Name}</h4>
        <table id="shifts">
        <thead>
          <th>Oncallers</th>
          <th>Start</th>
          <th>End</th>
          <th>Comment</th>
        <thead>
        <tbody>
            ${this.shiftsTemplate(s)}
        </tbody>
      `)}
      <br>
      <button type="button" @click=${() => (this.hide = true)}>Hide History
      </button>
      `;
  }

  render() {
    if (!this.datesFixed) {
      if (this.shifts && this.shifts.SplitShifts &&
        this.shifts.SplitShifts.length > 0) {
        this.toDateTime(this.shifts.SplitShifts);
        this.datesFixed = true;
      }
    }
    return html`
      <style>
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

        #shifts tr:nth-child(even){background-color: hsl(0, 0%, 95%);};
      </style>
      <fieldset>
        ${this.historyShifts()}
      </fieldset>
      </table>
      `;
  }
}

customElements.define('rota-shift-history', RotaShiftHistory);
