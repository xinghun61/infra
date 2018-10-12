import {LitElement, html} from '@polymer/lit-element';
import {DateTime} from 'luxon';
import * as constants from './constants';

class RotaShiftGenerate extends LitElement {
  static get properties() {
    return {
      shifts: {type: constants.Shifts},
      rota: {type: String},
      updateState: {},
    };
  }

  constructor() {
    super();
    this.datesFixed = false;
    this.generated = false;
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

  async generate() {
    const startElement = this.shadowRoot.getElementById('start').value;
    const numberElement = this.shadowRoot.getElementById('nrToSchedule').value;
    const generatorElement = this.shadowRoot.getElementById('generator').value;
    let formBody = new URLSearchParams();
    formBody.append('rota', this.rota);
    formBody.append('nrShifts', numberElement);
    formBody.append('startTime', startElement);
    formBody.append('generator', generatorElement);
    try {
      const res = await fetch('generate', {
        method: 'POST',
        body: formBody,
        headers: new Headers({
          'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }),
      });
      this.shifts = await res.json();
    } catch (err) {
      console.log(err);
      this.updateState = html`<small class="fail">${err}</small>`;
    }

    this.datesFixed = false;
    this.generated = true;
  }

  async sendJSON() {
    try {
      const res = await fetch('shiftsgenerate', {
        method: 'POST',
        body: JSON.stringify(this.shifts),
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (res.ok) {
        window.location.reload(true);
        return;
      }
      this.updateState = html`<small class="fail">res.statusText</small>`;
    } catch (err) {
      console.log(err);
      this.updateState = html`<small class="fail">${err}</small>`;
    }
  }

  selectOnCallers(ss, shift) {
    return shift.OnCall.map((oncall, oncallIdx) => html`
     <select name="shiftMember">
       <option value="${oncall.Email}">${oncall.Email}</option>
       ${ss.Members.map((o) => html`<option value=${o}>${o}</option>`)}
     </select>`);
  }

  renderShifts() {
    if (!this.shifts || !this.shifts.SplitShifts) {
      return;
    }
    return this.shifts.SplitShifts.map((s, splitIdx) => html`
      <h4>${s.Name}</h4>
      <table class="shifts">
      <thead>
        <th>Oncallers</th>
        <th>Start</th>
        <th>End</th>
        <th>Comment</th>
      <thead>
      <tbody>
        ${this.shiftsTemplate(s)}
      </tbody>
      </table>`);
  }

  shiftsTemplate(ss) {
    return ss.Shifts.map((i, shiftIdx) => html`
      <tr>
        <td>
        <table>
        <tbody>
        <td>
           ${this.selectOnCallers(ss, i)}
        </td>
        </tbody>
        </table>
        </td>
        <td>${i.StartTime.toFormat(constants.timeFormat)}</td>
        <td>${i.EndTime.toFormat(constants.timeFormat)}</td>
        <td>${i.Comment}</td>
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
        .shifts {
          font-size: small;
          border-collapse: collapse;
        }

        .shifts td, .shifts th {
          border: 1px, solid #ddd;
          padding: 8px;
        }

        .shifts th {
          text-align: left;
        }

        .ok {
          color: green;
          background-color: transparent;
        }

        .fail {
          color: red;
          background-color: transparent;
        }

        .shifts tr:nth-child(even) {
          background-color: hsl(0, 0%, 95%);
        };
      </style>
      <fieldset>
      <form>
        <table>
          <tbody>
            <tr>
              <td>StartDate:<input type="date" id="start"></td>
              <td>ShiftsToSchedule:<input type="number" id="nrToSchedule"></td>
              <td>Generator:<input type="text" id="generator" value="Fair"></td>
            </tr>
          </tbody>
        </table>
      </form>
      <button type="button" @click=${() => this.generate()}>Generate</button>
      ${this.generated ? html`
        <button type="button" @click=${() => this.sendJSON()}>Submit</button>
        <small>${this.updateState && this.updateState}</small>`: html``}
      <form>
        ${this.renderShifts()}
      </form>
      </fieldset>
      `;
  }
}

customElements.define('rota-shift-generate', RotaShiftGenerate);
