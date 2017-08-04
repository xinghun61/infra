'use strict';

class SomMarkedElement extends Polymer.Element {

  static get is() {
    return 'som-marked-element';
  }

  static get properties() {
    return {
      markdown: String,
      _markdownElement: Object,
    };
  }

  static get observers() {
    return [
      'render(markdown, _markdownElement)'
    ];
  }

  ready() {
    super.ready();

    this._markdownElement = this.$.markdownElement;
  }

  render(markdown, element) {
    if (!element) return;
    if (!markdown) {
      Polymer.dom(element).innerHTML = '';
      return;
    }
    let renderer = new marked.Renderer();
    renderer.link = this._getLinkRenderer();

    let opts = {
      renderer: renderer,
      breaks: true,
      sanitize: true,
      pedantic: false,
      smartypants: false
    };

    Polymer.dom(element).innerHTML = marked(markdown, opts);
  }

  _hrefIsAllowed(href) {
    // Marked does some URL sanitization in their default link renderer.
    // This copies Marked's sanitization for URLs so there is
    // not a loss in security.
    try {
      let prot = decodeURIComponent(unescape(href))
                     .replace(/[^\w:]/g, '')
                     .toLowerCase();
      if (prot.indexOf('javascript:') === 0 ||
          prot.indexOf('vbscript:') === 0 || prot.indexOf('data:') === 0) {
        return false;
      }
    } catch (e) {
      return false;
    }
    return true;
  }

  _getLinkRenderer() {
    return (href, title, text) => {
      if (!this._hrefIsAllowed(href))
        return text;
      return `<a href="${href}" target="_blank">${text}</a>`;
    };
  }
}

customElements.define(SomMarkedElement.is, SomMarkedElement);
