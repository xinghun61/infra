import {LitElement, html} from '@polymer/lit-element';

class RotaTestEmail extends LitElement {
  static get properties() {
    return {
      rota: {},
      email: {},
      emailStatus: {},
    };
  }

  async getJSON() {
    const rota = encodeURIComponent(this.rota);
    try {
      const res = await fetch(
        `/emailtest?name=${rota}`);
      if (!res.ok) {
        throw res;
      }
      this.email = await res.json();
      this.emailStatus = html`<small class="ok">(ok)</small>`;
    } catch (err) {
      this.emailStatus = html`<small class="fail">${err.text()}</small>`;
    }
  }

  fillEmail() {
    if (!this.email) {
      return html`<small><i>no data</i></amall>`;
    }
    return html`
      <b>Subject:</b>
      <br>
      <code class="border">${this.email.Subject}</code>
      <br>
      <b>Body:</b>
      <br>
      <code class="border">${this.email.Body}</code>
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

    code {
      display: block;
      white-space: pre-wrap;
    }

    .border {
      border-left-width: 4px;
      border-left-style: solid;
      border-left-color: #f3f3f3;
      background-color: #f8f8f8;
    };
    </style>
    ${this.fillEmail()}
    <br>
    <button type="button" @click=${() => this.getJSON()}>Test</button>
    ${this.emailStatus && this.emailStatus}
    `;
  };
}

customElements.define('rota-testemail', RotaTestEmail);
