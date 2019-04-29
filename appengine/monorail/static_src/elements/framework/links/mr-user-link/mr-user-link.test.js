// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrUserLink} from './mr-user-link.js';


let element;
let availabilityIcon;
let userLink;
let userText;
let availabilityText;

function getElements() {
  availabilityIcon = element.shadowRoot.querySelector(
    '#availability-icon');
  userLink = element.shadowRoot.querySelector(
    '#user-link');
  userText = element.shadowRoot.querySelector(
    '#user-text');
  availabilityText = element.shadowRoot.querySelector(
    '#availability-text');
}

suite('mr-user-link', () => {
  setup(() => {
    element = document.createElement('mr-user-link');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
  });

  test('initializes', () => {
    assert.instanceOf(element, MrUserLink);
  });

  test('no link when no userId and displayName is null value', async () => {
    element.userRef = {displayName: '----'};

    await element.updateComplete;
    getElements();

    assert.isFalse(userText.hidden);
    assert.equal(userText.textContent, '----');

    assert.isTrue(availabilityIcon.hidden);
    assert.isTrue(userLink.hidden);
    assert.isTrue(availabilityText.hidden);
  });

  test('link when displayName', async () => {
    element.userRef = {displayName: 'test@example.com'};

    await element.updateComplete;
    getElements();

    assert.isFalse(userLink.hidden);
    assert.equal(userLink.textContent.trim(), 'test@example.com');
    assert.isTrue(userLink.href.endsWith('/u/test@example.com'));

    assert.isTrue(availabilityIcon.hidden);
    assert.isTrue(userText.hidden);
    assert.isTrue(availabilityText.hidden);
  });

  test('link when userId', async () => {
    element.userRef = {userId: '1234', displayName: 'test@example.com'};

    await element.updateComplete;
    getElements();

    assert.isFalse(userLink.hidden);
    assert.equal(userLink.textContent.trim(), 'test@example.com');
    assert.isTrue(userLink.href.endsWith('/u/1234'));

    assert.isTrue(availabilityIcon.hidden);
    assert.isTrue(userText.hidden);
    assert.isTrue(availabilityText.hidden);
  });

  test('show availability', async () => {
    element.userRef = {userId: '1234', displayName: 'test@example.com'};
    element.referencedUsers = new Map(
      [['test@example.com', {availability: 'foo'}]]);
    element.showAvailabilityIcon = true;

    await element.updateComplete;
    getElements();

    assert.isFalse(availabilityIcon.hidden);
    assert.equal(availabilityIcon.title, 'foo');

    assert.isFalse(userLink.hidden);
    assert.isTrue(userText.hidden);
    assert.isTrue(availabilityText.hidden);
  });

  test('dont show availability', async () => {
    element.userRef = {userId: '1234', displayName: 'test@example.com'};
    element.referencedUsers = new Map(
      [['test@example.com', {availability: 'foo'}]]);

    await element.updateComplete;
    getElements();

    assert.isTrue(availabilityIcon.hidden);

    assert.isFalse(userLink.hidden);
    assert.isTrue(userText.hidden);
    assert.isTrue(availabilityText.hidden);
  });

  test('show availability text', async () => {
    element.userRef = {userId: '1234', displayName: 'test@example.com'};
    element.referencedUsers = new Map(
      [['test@example.com', {availability: 'foo'}]]);
    element.showAvailabilityText = true;

    await element.updateComplete;
    getElements();

    assert.isFalse(availabilityText.hidden);
    assert.equal(availabilityText.title, 'foo');
    assert.equal(availabilityText.textContent, 'foo');

    assert.isTrue(availabilityIcon.hidden);
    assert.isFalse(userLink.hidden);
    assert.isTrue(userText.hidden);
  });
});
