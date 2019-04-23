// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert, expect} from 'chai';
import {MrUserLink} from './mr-user-link.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';


let element;
let availabilityIcon;
let userLink;
let userText;
let availabilityText;

function getElements() {
  availabilityIcon = element.shadowRoot.querySelector(
    '#availabilityIcon');
  userLink = element.shadowRoot.querySelector(
    '#userLink');
  userText = element.shadowRoot.querySelector(
    '#userText');
  availabilityText = element.shadowRoot.querySelector(
    '#availabilityText');
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

  test('no link when no userId and displayName is null value', () => {
    element.userRef = {displayName: '----'};

    flush();
    getElements();

    assert.isNotNull(userText);
    assert.equal(userText.textContent, '----');

    assert.isNull(availabilityIcon);
    assert.isNull(userLink);
    assert.isNull(availabilityText);
  });

  test('link when displayName', () => {
    element.userRef = {displayName: 'test@example.com'};

    flush();
    getElements();

    assert.isNotNull(userLink);
    assert.equal(userLink.textContent.trim(), 'test@example.com');
    assert.isTrue(userLink.href.endsWith('/u/test@example.com'));

    assert.isNull(availabilityIcon);
    assert.isNull(userText);
    assert.isNull(availabilityText);
  });

  test('link when userId', () => {
    element.userRef = {userId: '1234', displayName: 'test@example.com'};

    flush();
    getElements();

    assert.isNotNull(userLink);
    assert.equal(userLink.textContent.trim(), 'test@example.com');
    assert.isTrue(userLink.href.endsWith('/u/1234'));

    assert.isNull(availabilityIcon);
    assert.isNull(userText);
    assert.isNull(availabilityText);
  });

  test('show availability', () => {
    element.userRef = {userId: '1234', displayName: 'test@example.com'};
    element.referencedUsers = new Map(
      [['test@example.com', {availability: 'foo'}]]);
    element.showAvailabilityIcon = true;

    flush();
    getElements();

    assert.isNotNull(availabilityIcon);
    assert.equal(availabilityIcon.title, 'foo');

    assert.isNotNull(userLink);
    assert.isNull(userText);
    assert.isNull(availabilityText);
  });

  test('dont show availability', () => {
    element.userRef = {userId: '1234', displayName: 'test@example.com'};
    element.referencedUsers = new Map(
      [['test@example.com', {availability: 'foo'}]]);

    flush();
    getElements();

    assert.isNull(availabilityIcon);

    assert.isNotNull(userLink);
    assert.isNull(userText);
    assert.isNull(availabilityText);
  });

  test('show availability text', () => {
    element.userRef = {userId: '1234', displayName: 'test@example.com'};
    element.referencedUsers = new Map(
      [['test@example.com', {availability: 'foo'}]]);
    element.showAvailabilityText = true;

    flush();
    getElements();

    assert.isNotNull(availabilityText);
    assert.equal(availabilityText.title, 'foo');
    assert.equal(availabilityText.textContent, 'foo');

    assert.isNull(availabilityIcon);
    assert.isNotNull(userLink);
    assert.isNull(userText);
  });
});
