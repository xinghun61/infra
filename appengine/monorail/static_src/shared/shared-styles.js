// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {css} from 'lit-element';

export const SHARED_STYLES = css`
  :host {
    --mr-edit-field-padding: 0.125em 4px;
    --mr-edit-field-width: 90%;
    --mr-input-grid-gap: 6px;
    --mr-content-heading-color: hsl(227, 60%, 39%);
  }

  .linkify {
    text-decoration: underline;
    color: var(--chops-link-color);
    display: inline;
    padding: 0;
    margin: 0;
    border: 0;
    background: 0;
    cursor: pointer;
  }
  h1, h2, h3, h4 {
    background: none;
  }
  a.button, .button {
    /* Links that look like buttons. */
    display: inline-flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    transition: filter 0.3s ease-in-out, box-shadow 0.3s ease-in-out;
  }
  a.button:hover, .button:hover {
    filter: brightness(95%);
  }
  chops-button, a.button, .button {
    box-sizing: border-box;
    font-size: var(--chops-main-font-size);
    background: white;
    border-radius: 6px;
    padding: 0.25em 8px;
    margin: 0;
    margin-left: auto;
    color: var(--chops-link-color);
  }
  chops-button i.material-icons, a.button i.material-icons, .button i.material-icons {
    display: block;
    margin-right: 4px;
  }
  chops-button.emphasized, a.button.emphasized, .button.emphasized {
    background: var(--chops-primary-button-bg);
    color: var(--chops-primary-button-color);
    text-shadow: 1px 1px 3px hsla(0, 0%, 0%, 0.25);
  }
  textarea, select, input {
    box-sizing: border-box;
    font-size: var(--chops-main-font-size);
  }
  /* Note: decoupling heading levels from styles is useful for
  * accessibility because styles will not always line up with semantically
  * appropriate heading levels.
  */
  .medium-heading {
    font-size: var(--chops-large-font-size);
    font-weight: normal;
    line-height: 1;
    padding: 0.25em 0;
    color: var(--mr-content-heading-color);
    margin: 0;
    margin-top: 0.25em;
    border-bottom: var(--chops-normal-border);
  }
  .medium-heading chops-button {
    line-height: 1.6;
  }
  .input-grid {
    padding: 0.5em 0;
    display: grid;
    max-width: 100%;
    grid-gap: var(--mr-input-grid-gap);
    grid-template-columns: minmax(120px, max-content) 1fr;
    align-items: flex-start;
  }
  .input-grid label {
    font-weight: bold;
    text-align: right;
    word-wrap: break-word;
  }
  @media (max-width: 600px) {
    .input-grid label {
      margin-top: var(--mr-input-grid-gap);
      text-align: left;
    }
    .input-grid {
      grid-gap: var(--mr-input-grid-gap);
      grid-template-columns: 100%;
    }
  }
`;
