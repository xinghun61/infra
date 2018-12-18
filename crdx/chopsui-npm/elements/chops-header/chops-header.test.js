import {assert} from 'chai';
import {ChopsHeader} from './chops-header.js';

let element;

suite('chops-header');

beforeEach(() => {
  element = document.createElement('chops-header');
  document.body.appendChild(element);
});

afterEach(() => {
  document.body.removeChild(element);
});

test('initializes', () => {
  assert.instanceOf(element, ChopsHeader);
});

test('changing appTitle sets title', async () => {
  element.appTitle = 'test';
  await element.updateComplete;
  const title = element.shadowRoot.querySelector('#title');
  assert.equal(title.textContent.trim(), 'test');
});
