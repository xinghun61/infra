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
 * Kibbles.Skipper is a Javascript library providing support for keyboard
 * navigation among DOM object on a page.
 */
(function(){

var _stops = new Array();  // list of stop objects
var _lastStop;  // id of the last stop we visited to.

// Named options. The value can be a literal value, or a function to call.
var _options = {
	padding_top: 0, // window offset when scrolling
  padding_bottom: 0,
  scroll_window: true
};

/*
 * Constants identifying listener types. Used with the method that
 * enables registration of listeners.
 */
var _LISTENER_TYPE = {
  PRE: 'pre',
  POST: 'post'
};

// map of stop listeners by type. pre listeners are called before navigation
// post listeners are called after navigation.
var _stopListener = {
	pre: [],
	post: []
};

/**
 * Remove all stop previously identified stop elements.
 */
function _reset() {
	_stops = new Array();
}

function _get(i) {
	return _stops[i];
}

function _set(i, element) {
	_stops[i] = element;
}

function _insert(i, element) {
  if (i < 0 || i > _stops.length - 1) {
    throw "Index out of bounds.";
  }
	_stops.splice(i, 0, element);
  if (i <= _lastStop) {
    _lastStop++;
  }
}

function _append(element) {
	_stops.push(element);
}

function _del(i) {
  if (i < 0 || i > _stops.length - 1) {
    throw "Index out of bounds.";
  }
	_stops.splice(i, 1);
  if (_lastStop >= i) {
    _lastStop--;
  }
}

function _length() {
	return _stops.length;
}

/**
 * Sets the named option to the specified value.
 */
function _setOption(name, value) {
	_options[name] = value;
}

/**
 * Register a key to move forward one stop.
 */
function _addFwdKey(character) {
	kibbles.keys.addKeyPressListener(character, _gotoNextStop);
}

/**
 * Register a key to move back one stop.
 */
function _addRevKey(character) {
	kibbles.keys.addKeyPressListener(character, _gotoPreviousStop);
}

/**
 * Adds a stop listener.
 */
function _addStopListener(type, handler) {
	if (type == _LISTENER_TYPE.PRE) {
		_stopListener.pre.push(handler);
	} else if (type == _LISTENER_TYPE.POST) {
		_stopListener.post.push(handler);
	}
}

/**
 * Scroll to next stop if any.
 */
function _gotoNextStop() {
	_setCurrentStop(_getNextStop());
}

/**
 * Scroll to previous stop if any.
 */
function _gotoPreviousStop() {
	_setCurrentStop(_getPreviousStop());
}

/**
 * Update the current and previous stops, scrolling window to the location
 * of the specified stop, and notifying listeners in the process.
 */
function _setCurrentStop(i) {
	if (i >= 0) {
		var prevStop = _lastStop;
		_lastStop = i;

    var next = new Stop(i);
    var prev = (prevStop >= 0) ? new Stop(prevStop) : undefined;

		_notifyListeners(next, prev, _stopListener.pre);

		// If the y coord of the stop was not previously determined
		// it may have been hidden. Since "PRE" listeners may reveal
		// hidden stops, we try again if "y" is not know.
		if (!next.y) next.y = _findObjectPosition(next.element);

		// if we can't id the y coords at this point, we throw an exception.
		if (!next.y && !(next.y >= 0)) {
			throw "Next stop does not y coords. Aborting.";
		}
		_notifyListeners(next, prev, _stopListener.post);
	}
}

/**
 * Called by a listener, not directly.
 */
function _scrollOpportunityListener(next, prev) {
  if (!_getOptionValue('scroll_window')) return;

  if (next && next.element) {

    var viewTop = _windowScrollTop();
    var viewBottom = viewTop + document.documentElement.clientHeight;

    var padTop = _getOptionValue('padding_top');

    var bottom = viewBottom - padTop;

    // if we skipped below the bottom padding
    if (next.y > bottom) {
      window.scrollTo(0, next.y - padTop);
      return;
    }

    var padBottom = _getOptionValue('padding_bottom');
    // if we skipped above the top offset
    var top = viewTop + padBottom;
    if (next.y < top) {
      window.scrollTo(0, (next.y - document.documentElement.clientHeight) + padBottom);
      return;
    }
  }
}

function _windowScrollTop() {
  if (window.document.body.scrollTop) {
    return window.document.body.scrollTop;
  } else if (window.document.documentElement.scrollTop) {
    return window.document.documentElement.scrollTop;
  } else if (window.pageYOffset) {
    return window.pageYOffset;
  }
  return 0;
}


/**
 * Returns an option value or if the value is a function,
 * the value returned by the function.
 */
function _getOptionValue(name) {
	var opt = _options[name];
	if (typeof opt == "function") {
		return opt();
	}
	return opt;
}

/**
 * Notify all supplied stop listeners.
 */
function _notifyListeners(stop, previousStop, listeners) {
	if (stop && listeners) {
		try {
			for (var i = 0; i < listeners.length; i++) {
				listeners[i](stop, previousStop);
			}
		} catch(err) {
			// don't let a grumpy listener bring us down.
		}
	}
}

/**
 * Returns the next stop or null if none stop available.
 */
function _getNextStop() {
	var i = 0;

	// if we've already visited a stop, use that as the base for the next stop.
	if (_lastStop >= 0) {
		i = _lastStop + 1;
	}

	// if the presumed next stop is out of bounds, return null.
	if (i > _stops.length - 1) {
		return;
	}
  return i;
}

/**
 * Returns the previous stop or null if none available.
 */
function _getPreviousStop() {
	var i = _stops.length - 1;

	// if we've already visited a stop, use that as the base for the next stop.
	if (_lastStop >= 0) {
		i = _lastStop - 1;
	}

	// if the presumed next stop is out of bounds, return null.
	if (i < 0) {
		return;
	}
  return i;
}

/**
 * Convenience wrapper for "stop" related information.
 */
function Stop(i, y) {
	this.index = i;
	this.element = _stops[i];
	this.y = _findObjectPosition(this.element);
}

/**
 * Returns the vertical coordinate of the top of specified object
 * relative to the top of the entire page.
 */
function _findObjectPosition(obj) {
	if (obj) {
		var curtop = 0;
		if (obj.offsetParent) {
			while (obj.offsetParent) {
				curtop += obj.offsetTop;
				obj = obj.offsetParent;
			}
		} else if (obj.y) {
			curtop += obj.y;
		}
		return curtop;
	}
	return null;
}

if (!window.kibbles.keys) {
  throw "Kibbles.Skipper requires Kibbles.Keys which is not loaded."
      + " Can't continue.";
}

/**
 * A nice little namespace to call our own.
 *
 * Formalizing Kibbles.Skipper as a traditional javascript class caused
 * headaches with respect to capturing the context (what is "this"
 * at any point in time). So we use a simple script exported via the
 * "kibbles.skipper" namespace.
 */
window.kibbles.skipper = {
	setOption: _setOption,
	addFwdKey: _addFwdKey,
	addRevKey: _addRevKey,
	LISTENER_TYPE: _LISTENER_TYPE,
	addStopListener: _addStopListener,
  setCurrentStop: _setCurrentStop,
	// array like methods for stop manipulation
	get: _get,
	set: _set,
	append: _append,
	insert: _insert,
	del: _del,
	length: _length,
	reset: _reset
}

_addStopListener(kibbles.skipper.LISTENER_TYPE.POST, _scrollOpportunityListener)

// we depend on kibbles.keys.
kibbles.keys.listen();

})();
