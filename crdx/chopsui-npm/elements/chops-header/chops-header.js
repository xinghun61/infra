import {LitElement, html} from '@polymer/lit-element/lit-element.js';

export class ChopsHeader extends LitElement {
  constructor() {
    super();
    this.appTitle = 'Chops App';
    this.homeUrl = '/';
  }

  static get properties() {
    return {
      /* String for the title of the application. */
      appTitle: {
        type: String,
      },
      /* The home URL for the application. Defaults to '/'. */
      homeUrl: {
        type: String,
      },
    };
  }

  render() {
    return html`
      <link
        href="https://fonts.googleapis.com/css?family=Roboto"
        rel="stylesheet"
      >
      <style>
        :host {
          box-sizing: border-box;
          position: fixed;
          background: white;
          font-family: 'Roboto', sans-serif;
          font-size: 16px;
          width: 100%;
          height: 50px;
          display: flex;
          flex-direction: row;
          justify-content: space-between;
          align-items: center;
          z-index: 100;
          border-bottom: 1px solid hsl(0, 0%, 88%);
        }
        ::slotted(img) {
          max-height: 100%;
        }
        a {
          text-decoration: none;
        }
        a:hover {
          text-decoration: underline;
        }
        .header-section {
          padding: 0 16px;
          height: 100%;
          display: flex;
          align-items: center;
        }
        #login {
          align-self: flex-end;
        }
        #title {
          font-size: 20px;
          display: flex;
          align-items: center;
          padding: 0 8px;
          height: 100%;
        }
      </style>
      <div class="header-section">
        <slot name="hamburger"></slot>
        <slot name="logo"></slot>
        <a id="title" href="${this.homeUrl}">
          ${this.appTitle}
        </a>
      </div>
      <div class="header-section">
        <slot></slot>
      </div>
      <div id="login" class="header-section">
        <slot name="login"></slot>
      </div>
    `;
  }
}

customElements.define('chops-header', ChopsHeader);
