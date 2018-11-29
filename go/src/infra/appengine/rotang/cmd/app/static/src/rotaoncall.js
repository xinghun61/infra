import {LitElement, html} from '@polymer/lit-element';
import {DateTime} from 'luxon';
import * as constants from './constants';
import humanizeDuration from 'humanize-duration';

const ShiftOnCall = {
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

const Rotas = {
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


class RotaOnCall extends LitElement {
  static get properties() {
    return {
      onCall: {type: ShiftOnCall},
      rotas: {type: Rotas},
      user: {},
      now: {},
    };
  };

  constructor() {
    super();
    this.datesFixed = false;
    this.needRefresh = true;
    this.now = DateTime.local();
    window.setInterval(() => {
      const now = DateTime.local();
      for (let o of this.onCall) {
        if (o.ShiftEndTime <= now) {
          this.refresh();
          break;
        }
      }
      this.now = now;
    }, 60000);
  }

  async sendJSON(req) {
    try {
      const res = await fetch('/oncalljson', {
        method: 'POST',
        body: JSON.stringify(req),
        headers: {
          'Content-Type': 'application/json',
        },
      });
      this.onCall = await res.json();
      this.datesFixed = false;
    } catch (err) {
      console.log(err);
    }
  }

  refresh() {
    let res = [];
    for (let rota of this.rotas) {
      res.push({
        'Name': rota,
        'At': DateTime.local(),
      });
    }
    this.sendJSON(res);
    this.needRefresh = false;
    this.datesFixed = false;
  }

  toDateTime(time) {
    for (let o of this.onCall) {
      o.Shift.StartTime = DateTime.fromISO(o.Shift.StartTime.toString())
        .setZone(constants.zone);
      o.Shift.EndTime = DateTime.fromISO(o.Shift.EndTime.toString())
        .setZone(constants.zone);
    }
  }

  shiftonCall(s) {
    if (!s.Shift.OnCall) {
      return;
    }
    return s.Shift.OnCall.map((o) => html`
      <div class='item'>
        ${this.handleUser(o)}
      </div>
    `);
  }

  onCallEntries(s) {
    if (!s.Shift.OnCall) {
      return html`
      <td>
      </td>
      <td>
      </td>
      <td>
      </td>
      `;
    }
    return html`
      <td>
        ${s.Shift.StartTime.toFormat(constants.timeFormat)}
      </td>
      <td>
        ${s.Shift.EndTime.toFormat(constants.timeFormat)}
      </td>
      <td>
        ${humanizeDuration(s.Shift.EndTime.diff(this.now).milliseconds,
    {largest: 2})}
      </td>
    `;
  }

  handleUser(o) {
    if (this.user === o.Email) {
      return html`<b>${o.Email}</b>`;
    }
    return html`${o.Email}`;
  }

  render() {
    if (this.rotas && this.needRefresh) {
      this.refresh();
    }
    if (this.onCall && !this.datesFixed) {
      this.toDateTime();
      this.datesFixed = true;
    }

    return html`
    <style>
      .flex-container {
        display: flex;
        margin: 0 -4px;
      }

      .item {
        margin: 0 4px;
      }

      .oncallers {
        font-size: small;
        border-collapse: collapse;
      }

      .oncallers td, .oncallers th {
        border: 1px, solid #ddd;
        padding: 8px;
      }

      .oncallers th {
        text-align: left;
      }

      .oncallers tr:nth-child(even) {
        background-color: hsl(0, 0%, 95%);
      };
    </style>
    <table class="oncallers">
      <thead>
        <th>Rota</th>
        <th>Oncallers</th>
        <th>Start</th>
        <th>End</th>
        <th>Time left</th>
      </thead>
      <tbody>
      ${this.onCall && this.onCall.map((s) => html`
        <tr>
          <td>
            <a href="/oncall/${s.Name}">${s.Name}</a>
          </td>
          <td>
            <div class="flex-container">
                ${this.shiftonCall(s)}
            <div>
          </td>
          ${this.onCallEntries(s)}
        </tr>`)}
      </tbody>
    </table>`
    ;
  }
}

customElements.define('rota-oncall', RotaOnCall);
