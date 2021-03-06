import {LitElement, html} from '@polymer/lit-element';
import * as constants from './constants';

class NavBar extends LitElement {
  static get properties() {
    return {
      page: {},
      logoutURL: {},
    };
  }

  constructor() {
    super();
  }

  home() {
    if (this.page === 'home') {
      return html`<li><a class="active" href="/">Home</a></li>`;
    }
    return html`<li><a href="/">Home</a></li>`;
  };

  rota() {
    if (this.page === 'rota') {
      return html`<li><a class="active" href="/managerota">Rotations</a></li>`;
    }
    return html`<li><a href="/managerota">Rotations</a></li>`;
  };

  oncall() {
    if (this.page === 'oncall') {
      return html`<li><a class="active" href="/oncall">Oncall</a></li>`;
    }
    return html`<li><a href="/oncall">Oncall</a></li>`;
  };

  migrate() {
    if (this.page === 'migrate') {
      return html`<li><a class="active" href="/switchlist">Migrate</a></li>`;
    }
    return html`<li><a href="/switchlist">Migrate</a></li>`;
  };

  logout() {
    return html`<li class="logout">
        <a style="background-color:#00d3f3"
          href="${this.logoutURL}">Logout</a>
      </li>`;
  };

  render() {
    return html`
    <style>
      ul {
        list-style-type: none;
        margin: 0;
        padding: 0;
        overflow: hidden;
        border: 1px solid #e7e7e7;
        background-color: #f3f3f3;
      }

      li {
        float: left;
      }

      li a {
        display: block;
        color: #666;
        text-align: center;
        padding: 14px 16px;
        text-decoration: none;
      }

      li a:hover:not(.active) {
        background-color: #111;
      }

      .active {
        background-color: #ddd;
      }

      .logout {
        float: right;
      }
    </style>
    <ul>
      ${this.home()}
      ${this.rota()}
      ${this.oncall()}
      ${this.migrate()}
      ${this.logout()}
    </ul>
    `;
  }
}

customElements.define('nav-bar', NavBar);
