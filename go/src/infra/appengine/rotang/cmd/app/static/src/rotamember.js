import {LitElement, html} from '@polymer/lit-element';
import {DateTime} from 'luxon';
import * as constants from './constants';

const MemberInfo = {
  fromAttribute: (value) => {
    let result;
    try {
      result = JSON.parse(value);
    } catch (x) {
      result = value;
      console.warn(`Could not JSON.parse value ${value}`);
    }
    return result;
  },
};

class RotaMember extends LitElement {
  static get properties() {
    return {
      info: {type: MemberInfo},
      addOOO: {},
      updateState: {},
      changed: {},
    };
  };

  constructor() {
    super();
    this.getJSON();
    this.addOOO = false;
    this.changed = false;
  }

  async getJSON() {
    try {
      const res = await fetch('/memberjson');
      if (!res.ok) {
        throw res;
      }
      this.info = await res.json();
      this.datesFixed = false;
    } catch (err) {
      console.error(err);
    }
  }

  async sendJSON() {
    try {
      const res = await fetch('/memberjson', {
        method: 'POST',
        body: JSON.stringify(this.info.Member),
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (!res.ok) {
        throw res;
      }
      this.updateState = html`<small class="ok">(OOO updated)</small>`;
    } catch (err) {
      console.log(err);
      this.updateState = html`<small class="fail">${err.text()}</small>`;
    }
  }

  rmOOO(idx) {
    this.info.Member.OOO = this.info.Member.OOO.slice(0, idx)
      .concat(this.info.Member.OOO.slice(idx+1));
    this.changed = true;
    this.requestUpdate();
  }

  addOOOInput() {
    const from = DateTime.fromISO(this.shadowRoot.getElementById('from').value)
      .setZone(constants.zone).plus({days: 1}).startOf('day');
    const to = DateTime.fromISO(this.shadowRoot.getElementById('to').value)
      .setZone(constants.zone).plus({days: 2}).startOf('day');
    const duration = to.diff(from).milliseconds;
    const comment = this.shadowRoot.getElementById('comment').value;

    if (!this.info) {
      return;
    }
    if (!this.info.Member.OOO) {
      this.info.Member.OOO = [];
    }
    this.info.Member.OOO = [...this.info.Member.OOO, {
      Start: from.setZone(constants.zone),
      Duration: duration * 10e6,
      Comment: comment,
    }];
    this.addOOO = false;
    this.changed = true;
  }

  ooo() {
    const oooForm = html`
    <form>
      <table>
        <thead>
          <th align="left">From</th>
          <th align="left">To</th>
          <th align="left">Comment</th>
        </thead>
        <tbody>
          <td><input type="date" id="from"></td>
          <td><input type="date" id="to"></td>
          <td><input type="text" id="comment"></td>
          <td><button type="button" @click=${() => this.addOOOInput()}>Add</td>
        </tbody>
      </table>
    </form>
    `;
    if (!this.info || !this.info.Member.OOO) {
      return this.oooForm(oooForm);
    }
    return html`
      <table id="ooo" class="ooo">
        <thead>
          <th align="left">From</th>
          <th align="left">To</th>
          <th align="left">Comment</th>
        </thead>
        <tbody>
          ${this.info.Member.OOO.map((ooo, idx) => html`
            <tr>
              <td>
                ${DateTime.fromISO(ooo.Start)
                    .setZone(constants.zone).toFormat(constants.timeFormat)}
              </td>
              <td>
                ${DateTime.fromISO(ooo.Start).setZone(constants.zone)
                    .plus(ooo.Duration/10e6).toFormat(constants.timeFormat)}
              </td>
              <td>${ooo.Comment}</td>
              <td>
                <button type="button" @click=${() =>
                    this.rmOOO(idx)}><small>&#x1F5D1;</small>
                </button>
              </td>
            </tr>
          `)}
        </tbody>
      </table>
      ${this.oooForm(oooForm)}
    `;
  }

  upcomingShifts() {
    if (!this.info || !this.info.Shifts) {
      return html`
        <b><i><small>none</small></i></b>
      `;
    }
    return html`
      <table id="shifts" class="ooo">
        <tbody>
          ${this.info.Shifts.map((s) => html`
            <tr>
              <td><a href="/oncall/${s.Name}">${s.Name}</a></td>
              <td>
                ${DateTime.fromISO(s.Entries[0].StartTime)
                  .setZone(constants.zone)
                  .toFormat(constants.timeFormat)}
              </td>
            </tr>
          `)}
        </tbody>
      </table>
    `;
  }

  oooForm(form) {
    if (this.addOOO) {
      return form;
    }
    return html`
      <a href="#!" @click="${() => {
        this.addOOO = true;
      }}">+</a>
    `;
  }

  oooChanged() {
    if (!this.changed) {
      return;
    }
    return html`
      <button type="button" @click=${() => this.sendJSON()}>Update</button>
      <small>${this.updateState && this.updateState}</small>
    `;
  }

  render() {
    return html`
    <style>
      .ooo {
        font-size: small;
        border-collapse: collapse;
      }

      .ooo td, .oncallers th {
        border: 1px, solid #ddd;
        padding: 8px;
      }

      .ooo th {
        text-align: left;
      }

      .ooo tr:nth-child(even) {
        background-color: hsl(0, 0%, 95%);
      }

      .ok {
        color: green;
        background-color: transparent;
      }

      .fail {
        color: red;
        background-color: transparent;
      }
      };
    </style>
    ${this.info && this.info.Member.full_name}
    <br>
    <h4>OOO ${this.oooChanged()}</h4>
    ${this.ooo()}
    <h4>Upcoming Shifts</h4>
    ${this.upcomingShifts()}
    `;
  }
}

customElements.define('rota-member', RotaMember);
