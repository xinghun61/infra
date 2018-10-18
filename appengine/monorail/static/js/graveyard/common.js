/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

// ------------------------------------------------------------------------
// This file contains common utilities and basic javascript infrastructure.
//
// Notes:
// * Press 'D' to toggle debug mode.
//
// Functions:
//
// - Assertions
// DEPRECATED: Use assert.js
// AssertTrue(): assert an expression. Throws an exception if false.
// Fail(): Throws an exception. (Mark block of code that should be unreachable)
// AssertEquals(): assert that two values are equal.
// AssertType(): assert that a value has a particular type
//
// - Cookies
// SetCookie(): Sets a cookie.
// ExpireCookie(): Expires a cookie.
// GetCookie(): Gets a cookie value.
//
// - Dynamic HTML/DOM utilities
// MaybeGetElement(): get an element by its id
// GetElement(): get an element by its id
// GetParentNode(): Get the parent of an element
// GetAttribute(): Get attribute value of a DOM node
// GetInnerHTML(): get the inner HTML of a node
// SetCssStyle(): Sets a CSS property of a node.
// GetStyleProperty(): Get CSS property from a style attribute string
// GetCellIndex(): Get the index of a table cell in a table row
// ShowElement(): Show/hide element by setting the "display" css property.
// ShowBlockElement(): Show/hide block element
// SetButtonText(): Set the text of a button element.
// AppendNewElement(): Create and append a html element to a parent node.
// CreateDIV(): Create a DIV element and append to the document.
// HasClass(): check if element has a given class
// AddClass(): add a class to an element
// RemoveClass(): remove a class from an element
//
// - Window/Screen utiltiies
// GetPageOffsetLeft(): get the X page offset of an element
// GetPageOffsetTop(): get the Y page offset of an element
// GetPageOffset(): get the X and Y page offsets of an element
// GetPageOffsetRight() : get X page offset of the right side of an element
// GetPageOffsetRight() : get Y page offset of the bottom of an element
// GetScrollTop(): get the vertical scrolling pos of a window.
// GetScrollLeft(): get the horizontal scrolling pos of a window
// IsScrollAtEnd():  check if window scrollbar has reached its maximum offset
// ScrollTo(): scroll window to a position
// ScrollIntoView(): scroll window so that an element is in view.
// GetWindowWidth(): get width of a window.
// GetWindowHeight(): get height of a window
// GetAvailScreenWidth(): get available screen width
// GetAvailScreenHeight(): get available screen height
// GetNiceWindowHeight(): get a nice height for a new browser window.
// Open{External/Internal}Window(): open a separate window
// CloseWindow(): close a window
//
// - DOM walking utilities
// AnnotateTerms(): find terms in a node and decorate them with some tag
// AnnotateText(): find terms in a text node and decorate them with some tag
//
// - String utilties
// HtmlEscape(): html escapes a string
// HtmlUnescape(): remove html-escaping.
// QuoteEscape(): escape " quotes.
// CollapseWhitespace(): collapse multiple whitespace into one whitespace.
// Trim(): trim whitespace on ends of string
// IsEmpty(): check if CollapseWhiteSpace(String) == ""
// IsLetterOrDigit(): check if a character is a letter or a digit
// ConvertEOLToLF(): normalize the new-lines of a string.
// HtmlEscapeInsertWbrs(): HtmlEscapes and inserts <wbr>s (word break tags)
//   after every n non-space chars and/or after or before certain special chars
//
// - TextArea utilities
// GetCursorPos(): finds the cursor position of a textfield
// SetCursorPos(): sets the cursor position in a textfield
//
// - Array utilities
// FindInArray(): do a linear search to find an element value.
// DeleteArrayElement(): return a new array with a specific value removed.
// CloneObject(): clone an object, copying its values recursively.
// CloneEvent(): clone an event; cannot use CloneObject because it
//               suffers from infinite recursion
//
// - Formatting utilities
// PrintArray(): used to print/generate HTML by combining static text
// and dynamic strings.
// ImageHtml(): create html for an img tag
// FormatJSLink(): formats a link that invokes js code when clicked.
// MakeId3(): formats an id that has two id numbers, eg, foo_3_7
//
// - Timeouts
// SafeTimeout(): sets a timeout with protection against ugly JS-errors
// CancelTimeout(): cancels a timeout with a given ID
// CancelAllTimeouts(): cancels all timeouts on a given window
//
// - Miscellaneous
// IsDefined(): returns true if argument is not undefined
// ------------------------------------------------------------------------

// browser detection
function BR_AgentContains_(str) {
  if (str in BR_AgentContains_cache_) {
    return BR_AgentContains_cache_[str];
  }

  return BR_AgentContains_cache_[str] =
    (navigator.userAgent.toLowerCase().indexOf(str) != -1);
}
// We cache the results of the indexOf operation. This gets us a 10x benefit in
// Gecko, 8x in Safari and 4x in MSIE for all of the browser checks
var BR_AgentContains_cache_ = {};

function BR_IsIE() {
  return (BR_AgentContains_('msie') || BR_AgentContains_('trident')) &&
         !window.opera;
}

function BR_IsKonqueror() {
  return BR_AgentContains_('konqueror');
}

function BR_IsSafari() {
  return BR_AgentContains_('safari') || BR_IsKonqueror();
}

function BR_IsNav() {
  return !BR_IsIE() &&
         !BR_IsSafari() &&
         BR_AgentContains_('mozilla');
}

var BACKSPACE_KEYCODE = 8;
var COMMA_KEYCODE = 188; // ',' key
var DEBUG_KEYCODE = 68; // 'D' key
var DELETE_KEYCODE = 46;
var DOWN_KEYCODE = 40; // DOWN arrow key
var ENTER_KEYCODE = 13; // ENTER key
var ESC_KEYCODE = 27; // ESC key
var LEFT_KEYCODE = 37; // LEFT arrow key
var RIGHT_KEYCODE = 39; // RIGHT arrow key
var SPACE_KEYCODE = 32; // space bar
var TAB_KEYCODE = 9; // TAB key
var UP_KEYCODE = 38; // UP arrow key
var SHIFT_KEYCODE = 16;
var PAGE_DOWN_KEYCODE = 34;
var PAGE_UP_KEYCODE = 33;

var MAX_EMAIL_ADDRESS_LENGTH = 320; // 64 + '@' + 255
var MAX_SIGNATURE_LENGTH = 1000; // 1000 chars of maximum signature

// ------------------------------------------------------------------------
// Assertions
// DEPRECATED: Use assert.js
// ------------------------------------------------------------------------
/**
 * DEPRECATED: Use assert.js
 */
function raise(msg) {
  if (typeof Error != 'undefined') {
    throw new Error(msg || 'Assertion Failed');
  } else {
    throw (msg);
  }
}

/**
 * DEPRECATED: Use assert.js
 *
 * Fail() is useful for marking logic paths that should
 * not be reached. For example, if you have a class that uses
 * ints for enums:
 *
 * MyClass.ENUM_FOO = 1;
 * MyClass.ENUM_BAR = 2;
 * MyClass.ENUM_BAZ = 3;
 *
 * And a switch statement elsewhere in your code that
 * has cases for each of these enums, then you can
 * "protect" your code as follows:
 *
 * switch(type) {
 *   case MyClass.ENUM_FOO: doFooThing(); break;
 *   case MyClass.ENUM_BAR: doBarThing(); break;
 *   case MyClass.ENUM_BAZ: doBazThing(); break;
 *   default:
 *     Fail("No enum in MyClass with value: " + type);
 * }
 *
 * This way, if someone introduces a new value for this enum
 * without noticing this switch statement, then the code will
 * fail if the logic allows it to reach the switch with the
 * new value, alerting the developer that he should add a
 * case to the switch to handle the new value he has introduced.
 *
 * @param {string} opt_msg to display for failure
 *                 DEFAULT: "Assertion failed"
 */
function Fail(opt_msg) {
  opt_msg = opt_msg || 'Assertion failed';
  if (IsDefined(DumpError)) DumpError(opt_msg + '\n');
  raise(opt_msg);
}

/**
 * DEPRECATED: Use assert.js
 *
 * Asserts that an expression is true (non-zero and non-null).
 *
 * Note that it is critical not to pass logic
 * with side-effects as the expression for AssertTrue
 * because if the assertions are removed by the
 * JSCompiler, then the expression will be removed
 * as well, in which case the side-effects will
 * be lost. So instead of this:
 *
 *  AssertTrue( criticalComputation() );
 *
 * Do this:
 *
 *  var result = criticalComputation();
 *  AssertTrue(result);
 *
 * @param expression to evaluate
 * @param {string} opt_msg to display if the assertion fails
 *
 */
function AssertTrue(expression, opt_msg) {
  if (!expression) {
    opt_msg = opt_msg || 'Assertion failed';
    Fail(opt_msg);
  }
}

/**
 * DEPRECATED: Use assert.js
 *
 * Asserts that a value is of the provided type.
 *
 *   AssertType(6, Number);
 *   AssertType("ijk", String);
 *   AssertType([], Array);
 *   AssertType({}, Object);
 *   AssertType(ICAL_Date.now(), ICAL_Date);
 *
 * @param value
 * @param type A constructor function
 * @param {string} opt_msg to display if the assertion fails
 */
function AssertType(value, type, opt_msg) {
  // for backwards compatability only
  if (typeof value == type) return;

  if (value || value == '') {
    try {
      if (type == AssertTypeMap[typeof value] || value instanceof type) return;
    } catch (e) {/* failure, type was an illegal argument to instanceof */}
  }
  let makeMsg = opt_msg === undefined;
  if (makeMsg) {
    if (typeof type == 'function') {
      let match = type.toString().match(/^\s*function\s+([^\s\{]+)/);
      if (match) type = match[1];
    }
    opt_msg = 'AssertType failed: <' + value + '> not typeof '+ type;
  }
  Fail(opt_msg);
}

var AssertTypeMap = {
  'string': String,
  'number': Number,
  'boolean': Boolean,
};

var EXPIRED_COOKIE_VALUE = 'EXPIRED';


// ------------------------------------------------------------------------
// Window/screen utilities
// TODO: these should be renamed (e.g. GetWindowWidth to GetWindowInnerWidth
// and moved to geom.js)
// ------------------------------------------------------------------------
// Get page offset of an element
function GetPageOffsetLeft(el) {
  let x = el.offsetLeft;
  if (el.offsetParent != null) {
    x += GetPageOffsetLeft(el.offsetParent);
  }
  return x;
}

// Get page offset of an element
function GetPageOffsetTop(el) {
  let y = el.offsetTop;
  if (el.offsetParent != null) {
    y += GetPageOffsetTop(el.offsetParent);
  }
  return y;
}

// Get page offset of an element
function GetPageOffset(el) {
  let x = el.offsetLeft;
  let y = el.offsetTop;
  if (el.offsetParent != null) {
    let pos = GetPageOffset(el.offsetParent);
    x += pos.x;
    y += pos.y;
  }
  return {x: x, y: y};
}

// Get the y position scroll offset.
function GetScrollTop(win) {
  return GetWindowPropertyByBrowser_(win, getScrollTopGetters_);
}

var getScrollTopGetters_ = {
  ieQuirks_: function(win) {
    return win.document.body.scrollTop;
  },
  ieStandards_: function(win) {
    return win.document.documentElement.scrollTop;
  },
  dom_: function(win) {
    return win.pageYOffset;
  },
};

// Get the x position scroll offset.
function GetScrollLeft(win) {
  return GetWindowPropertyByBrowser_(win, getScrollLeftGetters_);
}

var getScrollLeftGetters_ = {
  ieQuirks_: function(win) {
    return win.document.body.scrollLeft;
  },
  ieStandards_: function(win) {
    return win.document.documentElement.scrollLeft;
  },
  dom_: function(win) {
    return win.pageXOffset;
  },
};

// Scroll so that as far as possible the entire element is in view.
var ALIGN_BOTTOM = 'b';
var ALIGN_MIDDLE = 'm';
var ALIGN_TOP = 't';

var getWindowWidthGetters_ = {
  ieQuirks_: function(win) {
    return win.document.body.clientWidth;
  },
  ieStandards_: function(win) {
    return win.document.documentElement.clientWidth;
  },
  dom_: function(win) {
    return win.innerWidth;
  },
};

function GetWindowHeight(win) {
  return GetWindowPropertyByBrowser_(win, getWindowHeightGetters_);
}

var getWindowHeightGetters_ = {
  ieQuirks_: function(win) {
    return win.document.body.clientHeight;
  },
  ieStandards_: function(win) {
    return win.document.documentElement.clientHeight;
  },
  dom_: function(win) {
    return win.innerHeight;
  },
};

/**
 * Allows the easy use of different getters for IE quirks mode, IE standards
 * mode and fully DOM-compliant browers.
 *
 * @param win window to get the property for
 * @param getters object with various getters. Invoked with the passed window.
 * There are three properties:
 * - ieStandards_: IE 6.0 standards mode
 * - ieQuirks_: IE 6.0 quirks mode and IE 5.5 and older
 * - dom_: Mozilla, Safari and other fully DOM compliant browsers
 *
 * @private
 */
function GetWindowPropertyByBrowser_(win, getters) {
  try {
    if (BR_IsSafari()) {
      return getters.dom_(win);
    } else if (!window.opera &&
               'compatMode' in win.document &&
               win.document.compatMode == 'CSS1Compat') {
      return getters.ieStandards_(win);
    } else if (BR_IsIE()) {
      return getters.ieQuirks_(win);
    }
  } catch (e) {
    // Ignore for now and fall back to DOM method
  }

  return getters.dom_(win);
}

function GetAvailScreenWidth(win) {
  return win.screen.availWidth;
}

// Used for horizontally centering a new window of the given width in the
// available screen. Set the new window's distance from the left of the screen
// equal to this function's return value.
// Params: width: the width of the new window
// Returns: the distance from the left edge of the screen for the new window to
//   be horizontally centered
function GetCenteringLeft(win, width) {
  return (win.screen.availWidth - width) >> 1;
}

// Used for vertically centering a new window of the given height in the
// available screen. Set the new window's distance from the top of the screen
// equal to this function's return value.
// Params: height: the height of the new window
// Returns: the distance from the top edge of the screen for the new window to
//   be vertically aligned.
function GetCenteringTop(win, height) {
  return (win.screen.availHeight - height) >> 1;
}

/**
 * Opens a child popup window that has no browser toolbar/decorations.
 * (Copied from caribou's common.js library with small modifications.)
 *
 * @param url the URL for the new window (Note: this will be unique-ified)
 * @param opt_name the name of the new window
 * @param opt_width the width of the new window
 * @param opt_height the height of the new window
 * @param opt_center if true, the new window is centered in the available screen
 * @param opt_hide_scrollbars if true, the window hides the scrollbars
 * @param opt_noresize if true, makes window unresizable
 * @param opt_blocked_msg message warning that the popup has been blocked
 * @return {Window} a reference to the new child window
 */
function Popup(url, opt_name, opt_width, opt_height, opt_center,
  opt_hide_scrollbars, opt_noresize, opt_blocked_msg) {
  if (!opt_height) {
    opt_height = Math.floor(GetWindowHeight(window.top) * 0.8);
  }
  if (!opt_width) {
    opt_width = Math.min(GetAvailScreenWidth(window), opt_height);
  }

  let features = 'resizable=' + (opt_noresize ? 'no' : 'yes') + ',' +
                 'scrollbars=' + (opt_hide_scrollbars ? 'no' : 'yes') + ',' +
                 'width=' + opt_width + ',height=' + opt_height;
  if (opt_center) {
    features += ',left=' + GetCenteringLeft(window, opt_width) + ',' +
                'top=' + GetCenteringTop(window, opt_height);
  }
  return OpenWindow(window, url, opt_name, features, opt_blocked_msg);
}

/**
 * Opens a new window. Returns the new window handle. Tries to open the new
 * window using top.open() first. If that doesn't work, then tries win.open().
 * If that still doesn't work, prints an alert.
 * (Copied from caribou's common.js library with small modifications.)
 *
 * @param win the parent window from which to open the new child window
 * @param url the URL for the new window (Note: this will be unique-ified)
 * @param opt_name the name of the new window
 * @param opt_features the properties of the new window
 * @param opt_blocked_msg message warning that the popup has been blocked
 * @return {Window} a reference to the new child window
 */
function OpenWindow(win, url, opt_name, opt_features, opt_blocked_msg) {
  let newwin = OpenWindowHelper(top, url, opt_name, opt_features);
  if (!newwin || newwin.closed || !newwin.focus) {
    newwin = OpenWindowHelper(win, url, opt_name, opt_features);
  }
  if (!newwin || newwin.closed || !newwin.focus) {
    if (opt_blocked_msg) alert(opt_blocked_msg);
  } else {
    // Make sure that the window has the focus
    newwin.focus();
  }
  return newwin;
}

/*
 * Helper for OpenWindow().
 * (Copied from caribou's common.js library with small modifications.)
 */
function OpenWindowHelper(win, url, name, features) {
  let newwin;
  if (features) {
    newwin = win.open(url, name, features);
  } else if (name) {
    newwin = win.open(url, name);
  } else {
    newwin = win.open(url);
  }
  return newwin;
}

// ------------------------------------------------------------------------
// String utilities
// ------------------------------------------------------------------------
// Do html escaping
var amp_re_ = /&/g;
var lt_re_ = /</g;
var gt_re_ = />/g;

// converts multiple ws chars to a single space, and strips
// leading and trailing ws
var spc_re_ = /\s+/g;
var beg_spc_re_ = /^ /;
var end_spc_re_ = / $/;

var newline_re_ = /\r?\n/g;
var spctab_re_ = /[ \t]+/g;
var nbsp_re_ = /\xa0/g;

// URL-decodes the string. We need to specially handle '+'s because
// the javascript library doesn't properly convert them to spaces
var plus_re_ = /\+/g;

// Converts any instances of "\r" or "\r\n" style EOLs into "\n" (Line Feed),
// and also trim the extra newlines and whitespaces at the end.
var eol_re_ = /\r\n?/g;
var trailingspc_re_ = /[\n\t ]+$/;

// Converts a string to its canonicalized label form.
var illegal_chars_re_ = /[ \/(){}&|\\\"\000]/g;

// ------------------------------------------------------------------------
// TextArea utilities
// ------------------------------------------------------------------------

// Gets the cursor pos in a text area. Returns -1 if the cursor pos cannot
// be determined or if the cursor out of the textfield.
function GetCursorPos(win, textfield) {
  try {
    if (IsDefined(textfield.selectionEnd)) {
      // Mozilla directly supports this
      return textfield.selectionEnd;
    } else if (win.document.selection && win.document.selection.createRange) {
      // IE doesn't export an accessor for the endpoints of a selection.
      // Instead, it uses the TextRange object, which has an extremely obtuse
      // API. Here's what seems to work:

      // (1) Obtain a textfield from the current selection (cursor)
      let tr = win.document.selection.createRange();

      // Check if the current selection is in the textfield
      if (tr.parentElement() != textfield) {
        return -1;
      }

      // (2) Make a text range encompassing the textfield
      let tr2 = tr.duplicate();
      tr2.moveToElementText(textfield);

      // (3) Move the end of the copy to the beginning of the selection
      tr2.setEndPoint('EndToStart', tr);

      // (4) The span of the textrange copy is equivalent to the cursor pos
      let cursor = tr2.text.length;

      // Finally, perform a sanity check to make sure the cursor is in the
      // textfield. IE sometimes screws this up when the window is activated
      if (cursor > textfield.value.length) {
        return -1;
      }
      return cursor;
    } else {
      Debug('Unable to get cursor position for: ' + navigator.userAgent);

      // Just return the size of the textfield
      // TODO: Investigate how to get cursor pos in Safari!
      return textfield.value.length;
    }
  } catch (e) {
    DumpException(e, 'Cannot get cursor pos');
  }

  return -1;
}

function SetCursorPos(win, textfield, pos) {
  if (IsDefined(textfield.selectionEnd) &&
      IsDefined(textfield.selectionStart)) {
    // Mozilla directly supports this
    textfield.selectionStart = pos;
    textfield.selectionEnd = pos;
  } else if (win.document.selection && textfield.createTextRange) {
    // IE has textranges. A textfield's textrange encompasses the
    // entire textfield's text by default
    let sel = textfield.createTextRange();

    sel.collapse(true);
    sel.move('character', pos);
    sel.select();
  }
}

// ------------------------------------------------------------------------
// Array utilities
// ------------------------------------------------------------------------
// Find an item in an array, returns the key, or -1 if not found
function FindInArray(array, x) {
  for (let i = 0; i < array.length; i++) {
    if (array[i] == x) {
      return i;
    }
  }
  return -1;
}

// Delete an element from an array
function DeleteArrayElement(array, x) {
  let i = 0;
  while (i < array.length && array[i] != x) {
    i++;
  }
  array.splice(i, 1);
}

// Clean up email address:
// - remove extra spaces
// - Surround name with quotes if it contains special characters
// to check if we need " quotes
// Note: do not use /g in the regular expression, otherwise the
// regular expression cannot be reusable.
var specialchars_re_ = /[()<>@,;:\\\".\[\]]/;

// ------------------------------------------------------------------------
// Timeouts
//
// It is easy to forget to put a try/catch block around a timeout function,
// and the result is an ugly user visible javascript error.
// Also, it would be nice if a timeout associated with a window is
// automatically cancelled when the user navigates away from that window.
//
// When storing timeouts in a window, we can't let that variable be renamed
// since the window could be top.js, and renaming such a property could
// clash with any of the variables/functions defined in top.js.
// ------------------------------------------------------------------------
/**
 * Sets a timeout safely.
 * @param win the window object. If null is passed in, then a timeout if set
 *   on the js frame. If the window is closed, or freed, the timeout is
 *   automaticaaly cancelled
 * @param fn the callback function: fn(win) will be called.
 * @param ms number of ms the callback should be called later
 */
function SafeTimeout(win, fn, ms) {
  if (!win) win = window;
  if (!win._tm) {
    win._tm = [];
  }
  let timeoutfn = SafeTimeoutFunction_(win, fn);
  let id = win.setTimeout(timeoutfn, ms);

  // Save the id so that it can be removed from the _tm array
  timeoutfn.id = id;

  // Safe the timeout in the _tm array
  win._tm[id] = 1;

  return id;
}

/** Creates a callback function for a timeout*/
function SafeTimeoutFunction_(win, fn) {
  var timeoutfn = function() {
    try {
      fn(win);

      let t = win._tm;
      if (t) {
        delete t[timeoutfn.id];
      }
    } catch (e) {
      DumpException(e);
    }
  };
  return timeoutfn;
}

// ------------------------------------------------------------------------
// Misc
// ------------------------------------------------------------------------
// Check if a value is defined
function IsDefined(value) {
  return (typeof value) != 'undefined';
}

function GetKeyCode(event) {
  let code;
  if (event.keyCode) {
    code = event.keyCode;
  } else if (event.which) {
    code = event.which;
  }
  return code;
}
