import {LitElement, html} from '@polymer/lit-element';
import {DateTime} from 'luxon';
import * as constants from './constants';

class RotaShiftSwap extends LitElement {
  static get properties() {
    return {
      shifts: {type: constants.Shifts},
      updateState: {},
    };
  }

  constructor() {
    super();
    this.datesFixed = false;
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

  addMember(splitIdx, shiftIdx) {
    if (!this.shifts.SplitShifts[splitIdx].Shifts[shiftIdx].OnCall) {
      this.shifts.SplitShifts[splitIdx].Shifts[shiftIdx].OnCall = [];
    }
    let shift = this.shifts.SplitShifts[splitIdx].Shifts[shiftIdx];
    shift.OnCall = [...shift.OnCall, {
      Email: this.shifts.SplitShifts[splitIdx].Members[0],
      ShiftName: this.shifts.SplitShifts[splitIdx].Name,
    }];
    this.requestUpdate();
  }

  removeMember(splitIdx, shiftIdx, oncallIdx) {
    let shift = this.shifts.SplitShifts[splitIdx].Shifts[shiftIdx];
    shift.OnCall = shift.OnCall.slice(0, oncallIdx)
      .concat(shift.OnCall.slice(oncallIdx+1));
    this.requestUpdate();
  }

  fixComments() {
    for (let i = 0; i < this.shifts.SplitShifts.length; i++) {
      for (let j = 0; j < this.shifts.SplitShifts[i].Shifts.length; j++) {
        this.shifts.SplitShifts[i].Shifts[j].Comment =
          this.shadowRoot.getElementById(this.commentID(i, j)).value;
      }
    }
  }

  commentID(splitIDX, shiftIDX) {
    return `shiftComment_${splitIDX}-${shiftIDX}`;
  }

  async sendJSON() {
    this.fixComments();
    try {
      const res = await fetch('/shiftswap', {
        method: 'POST',
        body: JSON.stringify(this.shifts),
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (!res.ok) {
        throw res;
      }
      this.updateState = html`<small class="ok">(Shifts updated)</small>`;
    } catch (err) {
      this.updateState = html`<small class="fail">${err.text()}</small>`;
    }
  }

  selectOnCallers(splitIdx, shiftIdx, shift, members) {
    if (!shift.OnCall) {
      return;
    }
    return shift.OnCall.map((oncall, oncallIdx) => html`
      ${this.userOnCall(splitIdx, shiftIdx, oncallIdx, members, oncall)}
    `);
  }

  userOnCall(splitIdx, shiftIdx, oncallIdx, members, oncall) {
    if (!members) {
      return html`${oncall.Email}`;
    }
    if (members[0] === oncall.Email) {
      return html`<select name="shiftMember">
        <option value="${oncall.Email}">${oncall.Email}</option>
      </select>
      <button type="button" @click=${() =>
    this.removeMember(splitIdx, shiftIdx, oncallIdx)}>
      <small>-</small></button>
      `;
    }
    return html`<select name="shiftMember">
      <option value="${oncall.Email}">${oncall.Email}</option>
      <option value=${members[0]}>${members[0]}</option>
    </select>`;
  }

  currentShifts() {
    if (!this.shifts || !this.shifts.SplitShifts) {
      return;
    }
    return this.shifts.SplitShifts.map((s, splitIdx) => html`
    <h4>${s.Name}</h4>
      <table id="shifts">
      <thead>
        <th>Oncallers</th>
        <th>Start</th>
        <th>End</th>
       <th>Comment</th>
      <thead>
      <tbody>
        ${this.shiftTemplate(s, splitIdx)}
      </tbody>
      `);
  }

  shiftTemplate(ss, splitIdx) {
    return ss.Shifts.map((i, shiftIdx) => html`
      <tr>
        <td>
          ${this.selectOnCallers(splitIdx, shiftIdx, i, ss.Members)}
          <button type="button" @click=
            ${() => this.addMember(splitIdx, shiftIdx)}>
        <small>+</small>
        </button>
        </td>
        <td>
          <input type="text" name="shiftStart" class="roInput"
        value="${i.StartTime.toFormat(constants.timeFormat)}" readonly>
        </td>
        <td>
          <input type="text" name="shiftEnd" class="roInput"
        value="${i.EndTime.toFormat(constants.timeFormat)}" readonly>
        </td>
        <td>
          <input type=text id="${this.commentID(splitIdx, shiftIdx)}"
          value="${i.Comment}">
        </td>
      </tr>`);
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

        .roInput {
          font-size: small;
          border: 0px solid;
          background-color: transparent;
        }

        .ok {
          color: green;
          background-color: transparent;
        }

        .fail {
          color: red;
          background-color: transparent;
        }

        #shifts tr:nth-child(even) {
          background-color: hsl(0, 0%, 95%);
        };
      </style>
      <form action="swapshifts" method=POST>
        <fieldset>
          <legend>Current shifts</legend>
          ${this.currentShifts()}
            <br>
              <button type="button" @click=${() => this.sendJSON()}>
              Swap Shifts</button>
              <small>${this.updateState && this.updateState}</small>
          </table>
        </fieldset>
      </form>
      `;
  }
}

customElements.define('rota-shift-swap', RotaShiftSwap);
