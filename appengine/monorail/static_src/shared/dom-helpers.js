// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


// Prevent triggering input change handlers on key events that don't
// edit forms.
export const NON_EDITING_KEY_EVENTS = new Set(['Enter', 'Tab', 'Escape',
  'ArrowUp', 'ArrowLeft', 'ArrowRight', 'ArrowDown']);
const INPUT_TYPES_WITHOUT_TEXT_INPUT = [
  'checkbox',
  'radio',
  'file',
  'submit',
  'button',
  'image',
];
/**
 * Function to check if a keyboard event should be disabled if
 * the user is typing.
 *
 * @param {HTMLElement} element is a dom node to run checks against.
 * @return {boolean} Whether the dom node is an element that accepts key input.
 */
export function isTextInput(element) {
  const tagName = element.tagName && element.tagName.toUpperCase();
  if (tagName === 'INPUT') {
    const type = element.type.toLowerCase();
    if (INPUT_TYPES_WITHOUT_TEXT_INPUT.includes(type)) {
      return false;
    }
    return true;
  }
  return tagName === 'SELECT' || tagName === 'TEXTAREA'
    || element.isContentEditable;
}
