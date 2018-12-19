import {LitElement, html} from '@polymer/lit-element';

class RotaTestCal extends LitElement {
  static get properties() {
    return {
      rota: {},
      safe: {},
      calRes: {},
      calStatus: {},
    };
  }

  async getJSON() {
    const rota = encodeURIComponent(this.rota);
    try {
      const res = await fetch(`/caltest?name=${rota}`);
      if (!res.ok) {
        throw res;
      }
      this.calRes = await res.json();
      this.calStatus = html`<small class="ok">(ok)</small>`;
    } catch (err) {
      this.calStatus = html`<small class="fail">${err.text()}</small>`;
    }
  }

  success() {
    return html`
      <td class="ok">&#x2713;</td>
    `;
  }

  fail(message) {
    return html`
      <td class="fail">&#x2716; <small><i>${message}</i></small></td>
    `;
  }

  serviceState() {
    if (!this.calRes) {
      return html`<td><small><i>not yet tested</i></small></td>`;
    }
    if (this.calRes.Service.Success) {
      return this.success();
    }
    return this.fail(this.calRes.Service.Message);
  }

  legacyTest() {
    if (this.safe == 'false') {
      return html``;
    }
    return html`
    <tr>
      <td>Legacy calendar permissions</td>
      ${this.legacyState()}
    </tr>
    `;
  }

  legacyState() {
    if (!this.calRes) {
      return html`<td><small><i>not yet tested</i></small></td>`;
    }
    if (this.calRes.Legacy.Success) {
      return this.fail('calendar still shared with the legacy service');
    }
    return this.success();
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
    };
    </style>
    <table>
      <tbody>
        <tr>
          <td>RotaNG calendar permissions</td>
          ${this.serviceState()}
        </tr>
          ${this.legacyTest()}
      </tbody>
    </table>
    <button type="button" @click=${() => this.getJSON()}>Test</button>
    `;
  };
}

customElements.define('rota-testcal', RotaTestCal);
