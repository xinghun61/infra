import {LitElement, html} from '@polymer/lit-element';
import {DateTime, Duration} from 'luxon';
import * as constants from './constants';

const RotaConfig = {
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

class RotaCreate extends LitElement {
  static get properties() {
    return {
      config: {type: RotaConfig},
      generators: {type: RotaConfig},
      modifiers: {type: RotaConfig},
      members: {},
      shifts: {},
      showAddMember: {},
      showAddShift: {},
      memberEditIdx: {},
      updateState: {},
    };
  }

  constructor() {
    super();
    this.showAddMember = false;
    this.showAddShift = false;
    this.modify = true;
    this.configFixed = false;
  }

  rotaConfig() {
    if (this.configFixed) {
      return html`
      <table>
        <tbody>
          <tr>
            <td>
              Rotation Name:
            </td>
            <td>
              <input type="text" id="name" name="Name"
                value="${this.config.Cfg.Config.Name}"
              required>
                <small><i>changing this will make a copy of the rota</i></small>
            </td>
          </tr>
          <tr>
            <td>
              Description:
            </td>
            <td>
              <textarea id="description" class="text" cols="40" rows="4"
              >${this.config.Cfg.Config.Description}</textarea>
            </td>
          </tr>
          <tr>
            <td>
              Calendar:
            </td>
            <td>
              <input type="text" id="calendar" name="Calendar"
                value="${this.config.Cfg.Config.Calendar}">
            </td>
          </tr>
          <tr>
            <td>
              Owners:
            </td>
            <td>
              <input type="text" id="owners" name="Owners"
                value="${this.config.Cfg.Config.Owners}"
              required>
                <small><i> comma separated</i></small>
            </td>
          </tr>
          <tr>
            <td>
              Expiration:
            </td>
            <td>
              <input type="number" id="expiration" name="Expiration"
                value="${this.config.Cfg.Config.Expiration}"
              required>
                <small>
                  <i> Number of shifts remaining before generating new shifts</i>
                </small>
            </td>
          </tr>
          <tr>
            <td>
              Shifts To Schedule:
            </td>
            <td>
              <input type="number" id="shiftsToSchedule" name="ShiftsToSchedule"
                value=
                  "${this.config.Cfg.Config.ShiftsToSchedule}"
              required>
            </td>
          </tr>
          <tr>
            <td>
              Email Subject Template:
            </td>
            <td>
              <textarea id="emailSubjectTemplate" class="text" cols="40" rows="2"
                name="EmailSubjectTemplate"
                >${this.config.Cfg.Config.Email.Subject}</textarea>
            </td>
          </tr>
          <tr>
            <td>
              Email Body Template:
            </td>
            <td>
              <textarea id="emailBodyTemplate" class"text" cols="40" rows="10"
                name="EmailBodyTemplate"
                >${this.config.Cfg.Config.Email.Body}</textarea>
            </td>
          </tr>
          <tr>
            <td>
              Email Days Before Notify:
            </td>
            <td>
              <input id="emailNotify" type="number"  name="EmailNotify"
                value=
                  "${this.config.Cfg.Config.Email.DaysBeforeNotify}"
              required>
            </td>
          </tr>
        </tbody>
      </table>
    `;
    }
    return html`
    <table>
      <tbody>
        <tr>
          <td>
            Rotation Name:
          </td>
          <td>
            <input type="text" id="name" name="Name"
            required>
          </td>
        </tr>
        <tr>
          <td>
            Description:
          </td>
          <td>
            <textarea id="description" class="text" cols="40" rows="4"
            ></textarea>
          </td>
        </tr>
        <tr>
          <td>
            Calendar:
          </td>
          <td>
            <input type="text" id="calendar" name="Calendar" required>
          </td>
        </tr>
        <tr>
          <td>
            Owners:
          </td>
          <td>
            <input type="text" id="owners" name="Owners"
            required>
              <small><i> comma separated</i></small>
          </td>
        </tr>
        <tr>
          <td>
            Expiration:
          </td>
          <td>
            <input type="number" id="expiration" name="Expiration"
            required>
              <small>
                <i> Number of shifts remaining before generating new shifts</i>
              </small>
          </td>
        </tr>
        <tr>
          <td>
            Shifts To Schedule:
          </td>
          <td>
            <input type="number" id="shiftsToSchedule" name="ShiftsToSchedule"
            required>
          </td>
        </tr>
        <tr>
          <td>
            Email Subject Template:
          </td>
          <td>
            <textarea id="emailSubjectTemplate"
              class="text" cols="40" rows ="2" name="EmailSubjectTemplate"
            required></textarea>
          </td>
        </tr>
        <tr>
          <td>
            Email Body Template:
          </td>
          <td>
            <textarea id="emailBodyTemplate"
              class="text" cols="40" rows ="10" name="EmailBodyTemplate"
            required></textarea>
          </td>
        </tr>
        <tr>
          <td>
            Email Days Before Notify:
          </td>
          <td>
            <input id="emailNotify" type="number"  name="EmailNotify"
            required>
          </td>
        </tr>
      </tbody>
    </table>
  `;
  }

  rmMember(idx) {
    this.members = this.members.slice(0, idx)
      .concat(this.members.slice(idx+1));
    this.requestUpdate();
  }

  addMember() {
    if (!this.members) {
      this.members = [];
    }
    this.members = [...this.members, {
      Name: this.shadowRoot.getElementById('memberName').value,
      Email: this.shadowRoot.getElementById('memberEmail').value,
      Shift: this.shadowRoot.getElementById('memberShift').value,
      TZ: this.shadowRoot.getElementById('memberTZ').value,
    }];
    this.showAddMember = false;
  }

  editMember(idx) {
    this.members[idx].Name =
      this.shadowRoot.getElementById('editMemberName').value;
    this.members[idx].Shift =
      this.shadowRoot.getElementById('editMemberShift').value;
    this.members[idx].TZ =
      this.shadowRoot.getElementById('editMemberTZ').value;
    this.memberEditIdx = {};
  }

  getMember(idx) {
    if (this.memberEditIdx != idx) {
      return html`
        <td>${this.members[idx].Name}</td>
        <td>${this.members[idx].Email}</td>
        <td>${this.members[idx].Shift}</td>
        <td>${this.members[idx].TZ}</td>
        <td><button type="button" @click=${() => {
    this.memberEditIdx = idx;
  }}><small>&#x270E;</small></td>
        <td>
          <button type="button" @click=${() => this.rmMember(idx)}>
            <small>&#x1F5D1;</small>
          </button>
        </td>
      `;
    }
    return html`
      <td>
        <input type="text" id="editMemberName"
          value="${this.members[idx].Name}">
      </td>
      <td>
          ${this.members[idx].Email}
      </td>
      <td>
          <select id="editMemberShift">
            <option value="${this.members[idx].Shift}">
              ${this.members[idx].Shift}
            </option>
            ${this.shifts.map((s) => html`
              <option value="${s.Name}">${s.Name}</option>
            `)}
          </select>
      </td>
      <td>
          <select id="editMemberTZ">
            <option value="${this.members[idx].TZ}">
              ${this.members[idx].TZ}
            </option>
            ${constants.TimeZones.map((z) => html`
              <option value="${z.name}">${z.description}</option>
            `)}
          ${this.members[idx].TZ}
          </select>
      </td>
      <td>
        <button type="button" @click=${() => this.editMember(idx)}>
          <small>&#x2714;</small>
        </button>
      </td>
    `;
  }

  memberConfig() {
    if (!this.shifts) {
      return html`<i><b><small>add some shifts</small></b></i>`;
    }
    if (!this.members) {
      return this.addMemberForm();
    }

    return html`
      <table class="altrow">
        <thead>
          <th align="left">Name</th>
          <th align="left">Email</th>
          <th align="left">Shift</th>
          <th>TZ</th>
        </thead>
        <tbody>
            ${this.members.map((m, idx) => html`
              <tr>
                ${this.getMember(idx)}
              </tr>
            `)}
        </tbody>
      </table>
      <br>
      ${this.addMemberForm()}
    `;
  }

  addMemberForm() {
    const addMemberForm = html`
      Name: <input type="text" id="memberName">
      Email: <input type="email" id="memberEmail">
      Shift:
      <select id="memberShift">
        ${this.shifts && this.shifts.map((s) => html`
          <option value="${s.Name}">${s.Name}</option>
        `)}
      </select>
      TZ: <select id="memberTZ">
        ${constants.TimeZones.map((z) => html`
          <option value="${z.name}">${z.description}</option>
        `)}
      </select>
      <button type="button" @click=${() => this.addMember()}>Add</button>
    `;
    if (this.showAddMember) {
      return addMemberForm;
    }
    return html`
      <a href="#!" @click="${() => {
    this.showAddMember = true;
  }}">+</a>
    `;
  }

  rmShift(idx) {
    this.shifts = this.shifts.slice(0, idx)
      .concat(this.shifts.slice(idx+1));
    this.requestUpdate();
  }

  addShift() {
    if (!this.shifts) {
      this.shifts = [];
    }
    this.shifts = [...this.shifts, {
      Name: this.shadowRoot.getElementById('shiftName').value,
      Duration: this.shadowRoot.getElementById('shiftDuration').value,
    }];
    this.showAddShift = false;
  }

  shiftsList() {
    if (!this.shifts) {
      return this.addShiftForm();
    }
    return html`
      <table class="altrow">
        <thead>
          <th align="left">Name</th>
          <th align="left">Duration</th>
        </thead>
        <tbody>
          ${this.shifts.map((s, idx) => html`
            <tr>
              <td>${s.Name}</td>
              <td>${s.Duration}</td>
              <td>
                <button type="button" @click=${() => this.rmShift(idx)}>
                  <small>&#x1F5D1;</small>
                </button>
              </td>
            </tr>
          `)}
        </tbody>
      </table>
      <br>
      ${this.addShiftForm()}
    `;
  }

  addShiftForm() {
    const addShiftForm = html`
      Name: <input type="text" id="shiftName">
      Duration: <input type="number" id="shiftDuration">
      <button type="button" @click=${() => this.addShift()}>Add</button>
    `;
    if (this.showAddShift) {
      return addShiftForm;
    }
    return html`
      <a href="#!" @click="${() => {
    this.showAddShift = true;
  }}">+</a>
    `;
  }

  fillGenerators() {
    if (!this.configFixed) {
      return html`
        <select id="shiftGenerator" name="generator">
          ${this.generators && this.generators.map((g) => html`
            <option value="${g}" title="${g}">${g}</option>
            `)}
        </select>
      `;
    }
    return html`
      <select id="shiftGenerator" name="generator">
          <option value="${this.config.Cfg.Config.Shifts.Generator}">
          ${this.config.Cfg.Config.Shifts.Generator}</option>
        ${this.generators && this.generators.map((g) => html`
          <option value="${g}" title="${g}">${g}</option>
          `)}
      </select>
    `;
  }

  fillModifiers() {
    if (!this.modifiers) {
      return;
    }
    if (!this.configFixed) {
      return html`
        ${this.modifiers && this.modifiers.map((m, i) => html`
          <input type="checkbox" name="${m}"
            value="${m} id="modifier-${i}"><small>${m}</small><br>
        `)}
      `;
    }
    const res = this.modifiers.map((mod, i) => {
      const name = html`<small>${mod}</small><br>`;
      if (this.config.Cfg.Config.Shifts.Modifiers &&
        this.config.Cfg.Config.Shifts.Modifiers.indexOf(mod) != -1) {
        return html`<input type="checkbox" name="${mod}" value="${mod}"
          id="modifier-${i}" checked>${name}`;
      }
      return html`<input type="checkbox" name="${mod}" value="${mod}"
        id="modifier-${i}">${name}`;
    });
    return res;
  }

  shiftConfig() {
    return html`
      <table>
        <tbody>
          <tr>
            <td>
              StartTime:
            </td>
            <td>
              <input type="time"  id="shiftStart" name="shiftStart"
                value=
                  "${this.configFixed &&
                      this.config.Cfg.Config.Shifts.StartTime}"
              required>
              <small><i> MTV time</i></small>
            </td>
          </tr>
          <tr>
            <td>
              Length:
            </td>
            <td>
              <input type="number" id="shiftLength" name="shiftLength"
                value=
                  "${this.configFixed && this.config.Cfg.Config.Shifts.Length}"
              required>
              <small><i> Shift length in days</i></small>
            </td>
          </tr>
          <tr>
            <td>
              Skip:
            </td>
            <td>
              <input type="number" id="shiftSkip" name="shiftSkip"
                value="${this.configFixed &&
                  this.config.Cfg.Config.Shifts.Skip}"
              required>
              <small><i> Days to skip between shifts</i></small>
            </td>
          </tr>
          <tr>
            <td>
              ShiftMembers:
            </td>
            <td>
              <input type="number" id="shiftMembers" name="shiftMembers"
                value="${this.configFixed &&
                    this.config.Cfg.Config.Shifts.ShiftMembers}"
              required>
                <small><i> nr of members to schedule</i></small>
            </td>
          <tr><td>Modifiers:</td>
            <td>
              ${this.fillModifiers()}
            </td>
          <tr><td>Generator:</td>
            <td>
              ${this.fillGenerators()}
            </td>
          </tr>
        </tbody>
      </table>
      <h4>Shifts</h4>
        ${this.shiftsList()}
      `;
  }


  buildRotaMembers() {
    let rotaMembers = [];
    for (let i = 0; i < this.members.length; i++ ) {
      rotaMembers.push({
        ShiftName: this.members[i].Shift,
        Email: this.members[i].Email,
      });
    }
    return rotaMembers;
  }

  buildMembers() {
    let members = [];
    for (let i = 0; i < this.members.length; i++) {
      members.push({
        Name: this.members[i].Name,
        Email: this.members[i].Email,
        TZ: this.members[i].TZ,
      });
    }
    return members;
  }

  buildTime() {
    const inputTime = this.shadowRoot.getElementById('shiftStart').value;
    let hourMinute = inputTime.split(':');
    let dt = DateTime.fromObject({
      year: 2018,
      month: 9,
      day: 28,
      hour: Number(hourMinute[0]),
      minute: Number(hourMinute[1]),
      zone: constants.zone,
    });
    return dt;
  }

  buildOwners() {
    const inputOwners = this.shadowRoot.getElementById('owners').value;
    let splitOwners = inputOwners.split(',');
    for (let i = 0; i < splitOwners.length; i++) {
      splitOwners[i] = splitOwners[i].trim();
    }
    return splitOwners;
  }

  buildShifts() {
    let fixedShifts = [];
    for (let i = 0; i < this.shifts.length; i++) {
      fixedShifts.push({
        Name: this.shifts[i].Name,
        Duration: Duration.fromObject({hours: Number(this.shifts[i].Duration)})
          .as('milliseconds') * 10e5,
      });
    }
    return fixedShifts;
  }

  buildModifiers() {
    if (!this.modifiers) {
      return;
    }
    const modifiers = [];
    for (let i = 0; i < this.modifiers.length; i++) {
      if (this.shadowRoot.getElementById(`modifier-${i}`).checked) {
        modifiers.push(this.shadowRoot.getElementById(`modifier-${i}`).value);
      }
    }
    return modifiers;
  }

  async buildConfig() {
    const configuration = {
      Config: {
        Name: this.shadowRoot.getElementById('name').value,
        Description: this.shadowRoot.getElementById('description').value,
        Calendar: this.shadowRoot.getElementById('calendar').value,
        Owners: this.buildOwners(),
        Email: {
          Subject:
            this.shadowRoot.getElementById('emailSubjectTemplate').value,
          Body:
            this.shadowRoot.getElementById('emailBodyTemplate').value,
          DaysBeforeNotify:
            Number(this.shadowRoot.getElementById('emailNotify').value),
        },
        ShiftsToSchedule:
          Number(this.shadowRoot.getElementById('shiftsToSchedule').value),
        Shifts: {
          StartTime: this.buildTime(),
          Length: Number(this.shadowRoot.getElementById('shiftLength').value),
          Skip: Number(this.shadowRoot.getElementById('shiftSkip').value),
          ShiftMembers: Number(this.shadowRoot.getElementById('shiftMembers')
            .value),
          Generator: this.shadowRoot.getElementById('shiftGenerator').value,
          Modifiers: this.buildModifiers(),
          Shifts: this.buildShifts(),
        },
        Expiration: Number(this.shadowRoot.getElementById('expiration').value),
      },
      Members: this.buildRotaMembers(),
    };
    const membersAndConfig = {
      Cfg: configuration,
      Members: this.buildMembers(),
    };
    if (await this.sendJSON(membersAndConfig)) {
      const rota = encodeURIComponent(membersAndConfig.Cfg.Config.Name);
      if (!this.configFixed) {
        await this.sleep(2000);
        window.location.replace(
          `/modifyrota?name=${rota}`
        );
      }
    }
  }

  sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async sendJSON(cfg) {
    let url = '/createrota';
    if (this.configFixed) {
      url = '/modifyrota';
    }
    try {
      const res = await fetch(url, {
        method: 'POST',
        body: JSON.stringify(cfg),
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (!res.ok) {
        throw res;
      }
      this.updateState = html`<small class="ok">(Rotation updated)</small>`;
      return true;
    } catch (err) {
      this.updateState = html`<small class="fail">${err.text()}</small>`;
      return false;
    }
  }

  fixConfig() {
    if (!this.config || this.configFixed) {
      return;
    }
    this.members = [];
    for (let i = 0; i < this.config.Members.length; i++) {
      this.members.push({
        Name: this.config.Members[i].Name,
        Email: this.config.Members[i].Email,
        TZ: this.config.Members[i].TZ,
        Shift: this.config.Cfg.Members[i].ShiftName,
      });
    }
    this.shifts = [];
    for (let i = 0; i < this.config.Cfg.Config.Shifts.Shifts.length; i++) {
      this.shifts.push({
        Name: this.config.Cfg.Config.Shifts.Shifts[i].Name,
        Duration: this.config.Cfg.Config.Shifts.Shifts[i].Duration
          / (3600 * 10e8),
      });
    }
    let dt = DateTime.fromISO(this.config.Cfg.Config.Shifts.StartTime)
      .setZone(constants.zone);
    this.config.Cfg.Config.Shifts.StartTime = dt.toFormat('HH:mm');
    this.configFixed = true;
    let owners = '';
    for (let i = 0; i < this.config.Cfg.Config.Owners.length; i++) {
      owners = this.config.Cfg.Config.Owners[i] + ', ' + owners;
    }
    this.config.Cfg.Config.Owners = owners;
  }

  render() {
    this.fixConfig();
    return html`
  <style>
    .altrow {
      font-size: small;
      border-collapse: collapse;
    }

    .altrow td, .altrow th {
      border: 1px, solid #ddd;
      padding: 8px;
    }

    .altrow th {
      text-align: left;
    }

    .altrow tr:nth-child(even) {
      background-color: hsl(0, 0%, 95%);
    };

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

  </style>
  <form @submit="${() => {
    this.buildConfig();
    return false;
  }}" onsubmit="return false;" method="post">
  <fieldset>
    <legend>Modify rotation</legend>
    <fieldset>
    <legend>Rotation configuration</legend>
      ${this.rotaConfig()}
    </fieldset>
    <fieldset>
      <legend>Shift configuration</legend>
      ${this.shiftConfig()}
    </fieldset>
    <fieldset>
      <legend>Rotation members</legend>
      ${this.memberConfig()}
    </fieldset>
    <br>
    <input type="submit">
    <small>${this.updateState && this.updateState}</small>
  </fieldset>
</form>
    `;
  }
}

customElements.define('rota-create', RotaCreate);
