/**
 * Copyright 2008 Steve McKay.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * Kibbles.Keys is a Javascript library providing simple cross browser
 * keyboard event support.
 */
(function(){

var _listening = false;

// code to handler list map.
// Wildcard listeners use magic code wildcards "before" and "after".
var _listeners = {
	before: [],
	after: []
};

/*
 * Map of key names to char code. This map is consulted before
 * charCodeAt(0) is used to determine the character code.
 * 
 * This map also serves as a definitive list of supported "special" keys.
 * See _codeForEvent for details.
 */
var _CODE_MAP = {
	ESC: 27,
	ENTER: 13
};

/**
 * Register a keypress listener.
 */
function _listen() {
	if (_listening) return;

	var d = document;
	if (d.addEventListener) {
		d.addEventListener('keypress', _handleKeyboardEvent, false);
		d.addEventListener('keydown', _handleKeyDownEvent, false);
	} else if (d.attachEvent) {
		d.documentElement.attachEvent('onkeypress', _handleKeyboardEvent);
		d.documentElement.attachEvent('onkeydown', _handleKeyDownEvent);
	}
	_listening = true;
}

/**
 * Register a keypress listener for the supplied skip code.
 */
function _addKeyPressListener(spec, handler) {
	var code = spec.toLowerCase();
	if (code == "before" || code == "after") {
		_listeners[code].push(handler);
		return;
	}

	// try to find the character or key code.
	code = _CODE_MAP[spec.toUpperCase()];
	if (!code) {
		code = spec.charCodeAt(0);
	}
	if (!_listeners[code]) {
		_listeners[code] = [];
	}
	_listeners[code].push(handler);
}

/**
 * Our handler for keypress events.
 */
function _handleKeyboardEvent(e) {

	// If event is null, this is probably IE.
	if (!e) e = window.event;

	var source = _getSourceElement(e);
	if (_isInputElement(source)) {
		return;
	}

        if (_hasFlakeyModifier(e)) return;

	var code = _codeForEvent(e);

	if (code == undefined) return;

	var payload = {
		code: code
	};

	for (var i = 0; i < _listeners.before.length; i++) {
		_listeners.before[i](payload);
	}

	var listeners = _listeners[code];
	if (listeners) {
		for (var i = 0; i < listeners.length; i++) {
			listeners[i]({
				code: code
			});
		}
	}

	for (var i = 0; i < _listeners.after.length; i++) {
		_listeners.after[i](payload);
	}
}

function _handleKeyDownEvent(e) {
  if (!e) e = window.event;
  var code = _codeForEvent(e);
  if (code == _CODE_MAP['ESC'] || code == _CODE_MAP['ENTER']) {
    _handleKeyboardEvent(e);
  }
}

/**
 * Returns the keycode associated with the event.
 */
function _codeForEvent(e) {
  return e.keyCode ? e.keyCode : e.which;
}

/**
 * Returns true if the supplied event has an associated modifier key
 * that we have had trouble with in certain browsers.
 */
function _hasFlakeyModifier(e) {
	return e.altKey || e.ctrlKey || e.metaKey;
}

/**
 * Returns the source element for the supplied event.
 */
function _getSourceElement(e) {
	var element = e.target;
	if (!element) {
		element = e.srcElement;
	}

	if (element.shadowRoot) {
	    // Find the element within the shadowDOM.
	    element = e.path[0];
	}

	// If the source element is a text node, the parent is the object
	// we're interested in.
	if (element.nodeType == 3) {
		element = element.parentNode;
	}

	return element;
}

/**
 * Returns true if the element is a known form input element.
 */
function _isInputElement(element) {
	return element.tagName == 'INPUT' || element.tagName == 'TEXTAREA';
}

/*
 * A nice little namespace to call our own.
 *
 * Formalizing Kibbles.Keys as a traditional javascript class caused headaches
 * with respect to capturing the context (what is "this" at any point in time).
 * So we use a simple script exported via the "kibbles.keys" namespace.
 */
if (!window.kibbles)
	window.kibbles = {}

window.kibbles.keys = {
	listen: _listen,
	addKeyPressListener: _addKeyPressListener
};

})();
