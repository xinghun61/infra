/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * An autocomplete library for javascript.
 * Public API
 * - _ac_install() install global handlers required for everything else to
 *   function.
 * - _ac_register(SC) register a store constructor (see below)
 * - _ac_isCompleting() true iff focus is in an auto complete box and the user
 *   has triggered completion with a keystroke, and completion has not been
 *   cancelled (programatically or otherwise).
 * - _ac_isCompleteListShowing() true if _as_isCompleting and the complete list
 *   is visible to the user.
 * - _ac_cancel() if completing, stop it, otherwise a no-op.
 *
 *
 * A quick example
 *     // an auto complete store
 *     var myFavoritestAutoCompleteStore = new _AC_SimpleStore(
 *       ['some', 'strings', 'to', 'complete']);
 *
 *     // a store constructor
 *     _ac_register(function (inputNode, keyEvent) {
 *         if (inputNode.id == 'my-auto-completing-check-box') {
 *           return myFavoritestAutoCompleteStore;
 *         }
 *         return null;
 *       });
 *
 *     <html>
 *       <head>
 *         <script type=text/javascript src=ac.js></script>
 *       </head>
 *       <body onload=_ac_install()>
 *         <!-- the constructor above looks at the id.  It could as easily
 *            - look at the class, name, or value.
 *            - The autocomplete=off stops browser autocomplete from
 *            - interfering with our autocomplete
 *           -->
 *         <input type=text id="my-auto-completing-check-box"
 *          autocomplete=off>
 *       </body>
 *     </html>
 *
 *
 * Concepts
 * - Store Constructor function
 *   A store constructor is a policy function with the signature
 *     _AC_Store myStoreConstructor(
 *       HtmlInputElement|HtmlTextAreaElement inputNode, Event keyEvent)
 *   When a key event is received on a text input or text area, the autocomplete
 *   library will try each of the store constructors in turn until it finds one
 *   that returns an AC_Store which will be used for auto-completion of that
 *   text box until focus is lost.
 *
 * - interface _AC_Store
 *   An autocomplete store encapsulates all operations that affect how a
 *   particular text node is autocompleted.  It has the following operations:
 *   - String completable(String inputValue, int caret)
 *     This method returns null if not completable or the section of inputValue
 *     that is subject to completion.  If autocomplete works on items in a
 *     comma separated list, then the input value "foo, ba" might yield "ba"
 *     as the completable chunk since it is separated from its predecessor by
 *     a comma.
 *     caret is the position of the text cursor (caret) in the text input.
 *   - _AC_Completion[] completions(String completable,
 *                                  _AC_Completion[] toFilter)
 *     This method returns null if there are no completions.  If toFilter is
 *     not null or undefined, then this method may assume that toFilter was
 *     returned as a set of completions that contain completable.
 *   - String substitute(String inputValue, int caret,
 *                       String completable, _AC_Completion completion)
 *     returns the inputValue with the given completion substituted for the
 *     given completable.  caret has the same meaning as in the
 *     completable operation.
 *   - String oncomplete(boolean completed, int keycode,
 *                       HTMLElement element, String text)
 *     This method is called when the user hits a completion key. The default
 *     value is to do nothing, but you can override it if you want. Note that
 *     keycode will be null if the user clicked on it to select
 *   - Boolean autoselectFirstRow()
 *     This method returns True by default, but subclasses can override it
 *     to make autocomplete fields that require the user to press the down
 *     arrow or do a mouseover once before any completion option is considered
 *     to be selected.
 *
 * - class _AC_SimpleStore
 *   An implementation of _AC_Store that completes a set of strings given at
 *   construct time in a text field with a comma separated value.
 *
 * - struct _AC_Completion
 *   a struct with two fields
 *   - String value : the plain text completion value
 *   - String html : the value, as html, with the completable in bold.
 *
 * Key Handling
 * Several keys affect completion in an autocompleted input.
 * ESC - the escape key cancels autocompleting.  The autocompletion will have
 *   no effect on the focused textbox until it loses focus, regains it, and
 *   a key is pressed.
 * ENTER - completes using the currently selected completion, or if there is
 *   only one, uses that completion.
 * UP ARROW - selects the completion above the current selection.
 * DOWN ARROW - selects the completion below the current selection.
 *
 *
 * CSS styles
 * The following CSS selector rules can be used to change the completion list
 * look:
 * #ac-list               style of the auto-complete list
 * #ac-list .selected     style of the selected item
 * #ac-list b             style of the matching text in a candidate completion
 *
 * Dependencies
 * The library depends on the following libraries:
 * javascript:base for definition of key constants and SetCursorPos
 * javascript:shapes for nodeBounds()
 */

/**
 * install global handlers required for the rest of the module to function.
 */
function _ac_install() {
  ac_addHandler_(document.body, 'onkeydown', ac_keyevent_);
  ac_addHandler_(document.body, 'onkeypress', ac_keyevent_);
}

/**
 * register a store constructor
 * @param storeConstructor a function like
 *   _AC_Store myStoreConstructor(HtmlInputElement|HtmlTextArea, Event)
 */
function _ac_register(storeConstructor) {
  // check that not already registered
  for (var i = ac_storeConstructors.length; --i >= 0;) {
    if (ac_storeConstructors[i] === storeConstructor) { return; }
  }
  ac_storeConstructors.push(storeConstructor);
}

/**
 * may be attached as an onfocus handler to a text input to popup autocomplete
 * immediately on the box gaining focus.
 */
function _ac_onfocus(event) {
  ac_keyevent_(event);
}

/**
 * true iff the autocomplete widget is currently active.
 */
function _ac_isCompleting() {
  return !!ac_store && !ac_suppressCompletions;
}

/**
 * true iff the completion list is displayed.
 */
function _ac_isCompleteListShowing() {
  return !!ac_store && !ac_suppressCompletions && ac_completions &&
    ac_completions.length;
}

/**
 * cancel any autocomplete in progress.
 */
function _ac_cancel() {
  ac_suppressCompletions = true;
  ac_updateCompletionList(false);
}

/** add a handler without whacking any existing handler. @private */
function ac_addHandler_(node, handlerName, handler) {
  var oldHandler = node[handlerName];
  if (!oldHandler) {
    node[handlerName] = handler;
  } else {
    node[handlerName] = ac_fnchain_(node[handlerName], handler);
  }
  return oldHandler;
}

/** cancel the event. @private */
function ac_cancelEvent_(event) {
  if ('stopPropagation' in event) {
    event.stopPropagation();
  } else {
    event.cancelBubble = true;
  }

  // This is handled in IE by returning false from the handler
  if ('preventDefault' in event) {
    event.preventDefault();
  }
}

/** Call two functions, a and b, and return false if either one returns
    false.  This is used as a primitive way to attach multiple event
    handlers to an element without using addEventListener().   This
    library predates the availablity of addEventListener().
    @private
*/
function ac_fnchain_(a, b) {
  return function () {
    var ar = a.apply(this, arguments);
    var br = b.apply(this, arguments);

    // NOTE 1: (undefined && false) -> undefined
    // NOTE 2: returning FALSE from a onkeypressed cancels it,
    //         returning UNDEFINED does not.
    // As such, we specifically look for falses here
    if (ar === false || br === false) {
      return false;
    } else {
      return true;
    }
  }
}

/** key press handler.  @private */
function ac_keyevent_(event) {
  event = event || window.event;

  var source = event.target || event.srcElement;
  if (('INPUT' == source.tagName && source.type.match(/^text|email$/i))
       || 'TEXTAREA' == source.tagName) {
    var code = GetKeyCode(event);
    var isDown = event.type == 'keydown';
    var isShiftKey = event.shiftKey;
    var storeFound = true;

    if ((source !== ac_focusedInput) || (ac_store === null)) {
      ac_focusedInput = source;
      storeFound = false;
      if (ENTER_KEYCODE !== code && ESC_KEYCODE !== code) {
        for (var i = 0; i < ac_storeConstructors.length; ++i) {
          var store = (ac_storeConstructors[i])(source, event);
          if (store) {
            ac_store = store;
            ac_oldBlurHandler = ac_addHandler_(
                ac_focusedInput, 'onblur', _ac_ob);
            storeFound = true;
            break;
          }
        }

        // There exists an odd condition where an edit box with autocomplete
        // attached can be removed from the DOM without blur being called
        // In which case we are left with a store around that will try to
        // autocomplete the next edit box to receive focus. We need to clean
        // this up

        // If we can't find a store, force a blur
        if (!storeFound) {
          _ac_ob(null);
        }
      }
    }
    // If the user hit Escape when the auto-complete menu was not shown,
    // then blur the input text field so that the user can use keyboard
    // shortcuts.
    var acList = document.getElementById('ac-list');
    if (ESC_KEYCODE == code &&
        (!acList || acList.style.display == 'none')) {
      ac_focusedInput.blur();
    }
    if (storeFound) {
      var isCompletion = ac_store.isCompletionKey(code, isDown, isShiftKey);
      var hasResults = ac_completions && (ac_completions.length > 0);
      var cancelEvent = false;

      if (isCompletion && hasResults) {
        // Cancel any enter keystrokes if something is selected so that the
        // browser doesn't go submitting the form.
        cancelEvent = (!ac_suppressCompletions && !!ac_completions &&
                       (ac_selected != -1));
        window.setTimeout(function () {
          if (ac_store) { ac_handleKey_(code, isDown, isShiftKey); }
        }, 0);
      } else if (!isCompletion) {
       // Don't want to also blur the field. Up and down move the cursor (in
       // Firefox) to the start/end of the field. We also don't want that while
       // the list is showing.
       cancelEvent = (code == ESC_KEYCODE ||
                      code == DOWN_KEYCODE ||
                      code == UP_KEYCODE);

        window.setTimeout(function () {
          if (ac_store) { ac_handleKey_(code, isDown, isShiftKey); }
        }, 0);

      } else { // implicit if (isCompletion && !hasResults)
        if (ac_store.oncomplete) {
          ac_store.oncomplete(false, code, ac_focusedInput, undefined);
        }
      }

      if (cancelEvent) {
        ac_cancelEvent_(event);
      }

      return !cancelEvent;
    }
  }
  return true;
}

/** on blur handler. Since webkit gives spurious onblur events,
 *  so ignore all onblur and use a document-wide onclick instead. */
function _ac_ob(event) {
  // WebKit browsers: we use a document-wide on-click rather than blur events.
  if (!BR_hasExcessBlurEvents()) {
    _ac_real_onblur(event);
  }
}

/** Original autocomplete onblur handler. */
function _ac_real_onblur(event) {
  if (ac_focusedInput) {
    ac_focusedInput.onblur = ac_oldBlurHandler;
  }
  ac_store = null;
  ac_focusedInput = null;
  ac_everTyped = false;
  ac_oldBlurHandler = null;
  ac_suppressCompletions = false;
  ac_updateCompletionList(false);
}

/** This is a document-wide onclick handler that is only registered
 *  when using webkit browsers. It calls the real onblur handler
 *  when the user clicks away from a text field (or in many other
 *  situations where the user clicks, but that is OK). */
function _ac_fake_onblur(e) {
  var targ;
  if (!e) var e = window.event;
  if (e.target) targ = e.target;
  else if (e.srcElement) targ = e.srcElement;
  if (targ.nodeType == 3) { // Safari
    targ = targ.parentNode;
  }

  // If the user clicked anywhere other than one of the
  // form elements that can have its own autocomplete,
  // then close any open autocomplete menu.
  if ('INPUT' != targ.nodeName) {
    _ac_real_onblur(e);
  }
}


/** @constructor */
function _AC_Store() {
}
/** returns the chunk of the input to treat as completable. */
_AC_Store.prototype.completable = function (inputValue, caret) {
  console.log('UNIMPLEMENTED completable');
};
/** returns the chunk of the input to treat as completable. */
_AC_Store.prototype.completions = function (prefix, tofilter) {
  console.log('UNIMPLEMENTED completions');
};
/** returns the chunk of the input to treat as completable. */
_AC_Store.prototype.oncomplete = function (completed, keycode, element, text) {
  // Call the onkeyup handler so that choosing an autocomplete option has
  // the same side-effect as typing.  E.g., exposing the next row of input
  // fields.
  element.dispatchEvent(new Event('keyup'));
  _ac_real_onblur();
};
/** substitutes a completion for a completable in a text input's value. */
_AC_Store.prototype.substitute =
  function (inputValue, caret, completable, completion) {
  console.log('UNIMPLEMENTED substitute');
};
/** true iff hitting a comma key should complete. */
_AC_Store.prototype.commaCompletes = true;
/**
 * true iff the given keystroke should cause a completion (and be consumed in
 * the process.
 */
_AC_Store.prototype.isCompletionKey = function (code, isDown, isShiftKey) {
  if (!isDown && (ENTER_KEYCODE === code
                  || (AC_COMMA_KEYCODE == code && this.commaCompletes))) {
    return true;
  }
  if (TAB_KEYCODE === code && !isShiftKey) {
    // IE doesn't fire an event for tab on click in a text field, and firefox
    // requires that the onkeypress event for tab be consumed or it navigates
    // to next field.
    return false;
    //JER: return isDown == BR_IsIE();
  }
  return false;
};

function _AC_AddItemToFirstCharMap(firstCharMap, ch, s) {
  var l = firstCharMap[ch];
  if (!l) {
    l = firstCharMap[ch] = [];
  } else if (l[l.length - 1].value == s) {
    return;
  }
  l.push(new _AC_Completion(s, null, ''));
}

/**
 * an _AC_Store implementation suitable for completing lists of email
 * addresses.
 * @constructor
 */
function _AC_SimpleStore(strings, opt_docStrings) {
  this.firstCharMap_ = {};

  for (var i = 0; i < strings.length; ++i) {
    var s = strings[i];
    if (!s) { continue; }
    if (opt_docStrings && opt_docStrings[s]) {
      s = s + ' ' + opt_docStrings[s];
    }

    var parts = s.split(/\W+/);
    for (var j = 0; j < parts.length; ++j) {
      if (parts[j]) {
        _AC_AddItemToFirstCharMap(
            this.firstCharMap_, parts[j].charAt(0).toLowerCase(), strings[i]);
      }
    }
  }

  // The maximimum number of results that we are willing to show
  this.countThreshold = 2500;
  this.docstrings = opt_docStrings || {};
}
_AC_SimpleStore.prototype = new _AC_Store();
_AC_SimpleStore.prototype.constructor = _AC_SimpleStore;
_AC_SimpleStore.prototype.completable =
  function (inputValue, caret) {

  // complete after the last comma not inside ""s
  var start = 0;
  var state = 0;
  for (var i = 0; i < caret; ++i) {
    var ch = inputValue.charAt(i);
    switch (state) {
    case 0:
      if ('"' == ch) {
        state = 1;
      } else if (',' == ch || ' ' == ch) {
        start = i + 1;
      }
      break;
    case 1:
      if ('"' == ch) {
        state = 0;
      }
      break;
    }
  }
  while (start < caret &&
         ' \t\r\n'.indexOf(inputValue.charAt(start)) >= 0) {
    ++start;
  }
  return inputValue.substring(start, caret);
};


/** Simple function to create a <span> with matching text in bold.
 */
function _AC_CreateSpanWithMatchHighlighted(match) {
    var span = document.createElement('span');
    span.appendChild(document.createTextNode(match[1] || ''));
    var bold = document.createElement('b');
    span.appendChild(bold);
    bold.appendChild(document.createTextNode(match[2]));
    span.appendChild(document.createTextNode(match[3] || ''));
    return span;
};


/**
 * Get all completions matching the given prefix.
 * @param {string} prefix The prefix of the text to autocomplete on.
 * @param {List.<string>?} toFilter Optional list to filter on. Otherwise will
 *     use this.firstCharMap_ using the prefix's first character.
 * @return {List.<_AC_Completion>} The computed list of completions.
 */
_AC_SimpleStore.prototype.completions = function(prefix, toFilter) {
  if (!prefix) {
    return [];
  }
  if ((toFilter == null) || (toFilter.length == 0)) {
    toFilter = this.firstCharMap_[prefix.charAt(0).toLowerCase()];
  }

  // Since we use prefix to build a regular expression, we need to escape RE
  // characters. We match '-', '{', '$' and others in the prefix and convert
  // them into "\-", "\{", "\$".
  var regexForRegexCharacters = /([\^*+\-\$\\\{\}\(\)\[\]\#?\.])/g;
  var modifiedPrefix = prefix.replace(regexForRegexCharacters, '\\$1');

  // Match the modifiedPrefix anywhere as long as it is either at the very
  // beginning "Th" -> "The Hobbit", or comes immediately after a word separator
  // such as "Ga" -> "The-Great-Gatsby".
  var patternRegex = '^(.*\\W)?(' + modifiedPrefix + ')(.*)';
  var pattern = new RegExp(patternRegex, 'i' /* ignore case */);

  // We keep separate lists of possible completions that were generated
  // by matching a value or generated by matching a docstring.  We return
  // a concatenated list so that value matches all come before docstring
  // matches.
  var completions = [];
  var docCompletions = [];

  if (toFilter) {
    var toFilterLength = toFilter.length;
    for (var i = 0; i < toFilterLength; ++i) {
      var docStr = this.docstrings[toFilter[i].value];
      var compSpan = null;
      var docSpan = null;
      var matches = toFilter[i].value.match(pattern);
      var docMatches = docStr && docStr.match(pattern);
      if (matches) {
        compSpan = _AC_CreateSpanWithMatchHighlighted(matches);
        if (docStr) docSpan = document.createTextNode(docStr);
      } else if (docMatches) {
        compSpan = document.createTextNode(toFilter[i].value);
        docSpan = _AC_CreateSpanWithMatchHighlighted(docMatches);
      }

      if (compSpan) {
        var newCompletion = new _AC_Completion(
            toFilter[i].value, compSpan, docSpan);

        if (matches) {
          completions.push(newCompletion);
        } else {
          docCompletions.push(newCompletion);
        }
        if (completions.length + docCompletions.length > this.countThreshold) {
          break;
        }
      }
    }
  }

  return completions.concat(docCompletions);
};

// Normally, when the user types a few characters, we aggressively
// select the first possible completion (if any).  When the user
// hits ENTER, that first completion is substituted.  When that
// behavior is not desired, override this to return false.
_AC_SimpleStore.prototype.autoselectFirstRow = function () {
  return true;
};

// Comparison function for _AC_Completion
function _AC_CompareACCompletion(a, b) {
  // convert it to lower case and remove all leading junk
  var aval = a.value.toLowerCase().replace(/^\W*/,'');
  var bval = b.value.toLowerCase().replace(/^\W*/,'');

  if (a.value === b.value) {
    return 0;
  } else if (aval < bval) {
    return -1;
  } else {
    return 1;
  }
}

_AC_SimpleStore.prototype.substitute =
function (inputValue, caret, completable, completion) {
  return inputValue.substring(0, caret - completable.length) +
    completion.value + ', ' + inputValue.substring(caret);
};

/**
 * a possible completion.
 * @constructor
 */
function _AC_Completion(value, compSpan, docSpan) {
  /** plain text. */
  this.value = value;
  if (typeof compSpan == 'string') compSpan = document.createTextNode(compSpan);
  this.compSpan = compSpan;
  if (typeof docSpan == 'string') docSpan = document.createTextNode(docSpan);
  this.docSpan = docSpan;
}
_AC_Completion.prototype.toString = function () {
  return '(AC_Completion: ' + this.value + ')';
};

/** registered store constructors.  @private */
var ac_storeConstructors = [];
/**
 * the focused text input or textarea whether store is null or not.
 * A text input may have focus and this may be null iff no key has been typed in
 * the text input.
 */
var ac_focusedInput = null;
/**
 * null or the autocomplete store used to compelte ac_focusedInput.
 * @private
 */
var ac_store = null;
/** store handler from ac_focusedInput. @private */
var ac_oldBlurHandler = null;
/**
 * true iff user has indicated completions are unwanted (via ESC key)
 * @private
 */
var ac_suppressCompletions = false;
/**
 * chunk of completable text seen last keystroke.
 * Used to generate ac_completions.
 * @private
 */
var ac_lastCompletable = null;
/** an array of _AC_Completions.  @private */
var ac_completions = null;
/** -1 or in [0, _AC_Completions.length).  @private */
var ac_selected = -1;

/** Maxium number of options dislpayed in menu. @private */
var ac_max_options = 100;

/**
 * handles all the key strokes, updating the completion list, tracking selected
 * element, performing substitutions, etc.
 * @private
 */
function ac_handleKey_(code, isDown, isShiftKey) {
  // check completions
  ac_checkCompletions();
  var show = true;
  var numCompletions = ac_completions ? ac_completions.length : 0;
  // handle enter and tab on key press and the rest on key down
  if (ac_store.isCompletionKey(code, isDown, isShiftKey)) {
    if (ac_selected < 0 && numCompletions >= 1 &&
        ac_store.autoselectFirstRow()) {
      ac_selected = 0;
    }
    if (ac_selected >= 0) {
      var backupInput = ac_focusedInput;
      var completeValue = ac_completions[ac_selected].value;
      ac_complete();
      if (ac_store.oncomplete) {
        ac_store.oncomplete(true, code, backupInput, completeValue);
      }
    }
  } else {
    switch (code) {
    case ESC_KEYCODE:  // escape
      //JER?? ac_suppressCompletions = true;
      ac_selected = -1;
      show = false;
      break;
    case UP_KEYCODE:  // up
      if (isDown) {
        // firefox fires arrow events on both down and press, but IE only fires
        // then on press.
        ac_selected = Math.max(numCompletions >= 0 ? 0 : -1, ac_selected - 1);
      }
      break;
    case DOWN_KEYCODE:  // down
      if (isDown) {
         ac_selected = Math.min(
              ac_max_options - 1, Math.min(numCompletions - 1, ac_selected + 1));
      }
      break;
    }

    if (isDown) {
      switch (code) {
      case ESC_KEYCODE:
      case ENTER_KEYCODE:
      case UP_KEYCODE:
      case DOWN_KEYCODE:
      case RIGHT_KEYCODE:
      case LEFT_KEYCODE:
      case TAB_KEYCODE:
      case SHIFT_KEYCODE:
      case BACKSPACE_KEYCODE:
      case DELETE_KEYCODE:
        break;
      default:  // User typed some new characters.
        ac_everTyped = true;
      }
    }

  }

  if (ac_focusedInput) {
    ac_updateCompletionList(show);
  }
}

/**
 * called when an option is clicked on to select that option.
 */
function _ac_select(optionIndex) {
  ac_selected = optionIndex;
  ac_complete();
  if (ac_store.oncomplete) {
    ac_store.oncomplete(true, null, ac_focusedInput, ac_focusedInput.value);
  }

  // check completions
  ac_checkCompletions();
  ac_updateCompletionList(true);
}

function _ac_mouseover(optionIndex) {
  ac_selected = optionIndex;
  ac_updateCompletionList(true);
}

/** perform the substitution of the currently selected item. */
function ac_complete() {
  var caret = ac_getCaretPosition_(ac_focusedInput);
  var completion = ac_completions[ac_selected];

  ac_focusedInput.value = ac_store.substitute(
      ac_focusedInput.value, caret,
      ac_lastCompletable, completion);
  // When the prefix starts with '*' we want to return the complete set of all
  // possible completions. We treat the ac_lastCompletable value as empty so
  // that the caret is correctly calculated (i.e. the caret should not consider
  // placeholder values like '*member').
  var new_caret = caret + completion.value.length;
  if (!ac_lastCompletable.startsWith('*')) {
    // Only consider the ac_lastCompletable length if it does not start with '*'
    new_caret = new_caret - ac_lastCompletable.length
  }
  // If we inserted something ending in two quotation marks, position
  // the cursor between the quotation marks. If we inserted a complete term,
  // skip over the trailing space so that the user is ready to enter the next
  // term.  If we inserted just a search operator, leave the cursor immediately
  // after the colon or equals and don't skip over the space.
  if (completion.value.substring(completion.value.length - 2) == '""') {
    new_caret--;
  } else if (completion.value.substring(completion.value.length - 1) != ':' &&
             completion.value.substring(completion.value.length - 1) != '=') {
    new_caret++;  // To account for the comma.
    new_caret++;  // To account for the space after the comma.
  }
  ac_selected = -1;
  ac_completions = null;
  ac_lastCompletable = null;
  ac_everTyped = false;
  SetCursorPos(window, ac_focusedInput, new_caret);
}

/**
 * True if the user has ever typed any actual characters in the currently
 * focused text field.  False if they have only clicked, backspaced, and
 * used the arrow keys.
 */
var ac_everTyped = false;

/**
 * maintains ac_completions, ac_selected, ac_lastCompletable.
 * @private
 */
function ac_checkCompletions() {
  if (!ac_suppressCompletions) {
    var caret = ac_getCaretPosition_(ac_focusedInput);
    var completable = ac_store.completable(ac_focusedInput.value, caret);

    // If we already have completed, then our work here is done.
    if (completable == ac_lastCompletable) { return; }
    var tofilter;
    if (ac_lastCompletable &&
        ac_lastCompletable.length < completable.length &&
        completable.substring(0, ac_lastCompletable.length) ==
        ac_lastCompletable) {
      tofilter = ac_completions;
    } else {
      ac_completions = null;
      ac_selected = -1;
    }

    var oldSelected =
      (ac_selected >= 0) ? ac_completions[ac_selected].value : null;
    ac_completions = ac_store.completions(completable, tofilter);
    ac_selected = oldSelected ? 0 : -1;
    ac_lastCompletable = completable;
    return;
  }
  ac_lastCompletable = null;
  ac_completions = null;
  ac_selected = -1;
}

/**
 * maintains the completion list GUI.
 * @private
 */
function ac_updateCompletionList(show) {
  var clist = document.getElementById('ac-list');
  if (show && ac_completions && ac_completions.length) {
    if (!clist) {
      clist = document.createElement('DIV');
      clist.id = 'ac-list';
      clist.style.position = 'absolute';
      clist.style.display = 'none';
      document.body.appendChild(clist);
    }

    // If no choice is selected, then select the first item, if desired.
    if (ac_selected < 0 && ac_store && ac_store.autoselectFirstRow()) {
      ac_selected = 0;
    }

    var headerCount= 0;
    var tableEl = document.createElement('table');
    tableEl.setAttribute('cellpadding', 0);
    tableEl.setAttribute('cellspacing', 0);
    for (var i = 0; i < Math.min(ac_max_options, ac_completions.length); ++i) {
      if (ac_completions[i].heading) {
        var rowEl = document.createElement('tr');
        tableEl.appendChild(rowEl);
        var cellEl = document.createElement('th');
        rowEl.appendChild(cellEl);
        cellEl.setAttribute('colspan', 2);
        if (headerCount) {
            cellEl.appendChild(document.createElement('br'));
        }
        cellEl.appendChild(
            document.createTextNode(ac_completions[i].heading));
        headerCount++;
      } else {
        var rowEl = document.createElement('tr');
        tableEl.appendChild(rowEl);
        if (i == ac_selected) {
          rowEl.id = 'ac-selected-row';
          rowEl.className = 'selected';
        }
        rowEl.setAttribute('data-index', i);
        rowEl.addEventListener('mousedown', function(event) {
          event.preventDefault();
        });
        rowEl.addEventListener('mouseup', function(event) {
            var target = event.target;
            while (target && target.tagName != 'TR')
              target = target.parentNode;
            var idx = Number(target.getAttribute('data-index'));
            try {
              _ac_select(idx);
            } finally {
              return false;
            }
        });
        rowEl.addEventListener('mouseover', function(event) {
            var target = event.target;
            while (target && target.tagName != 'TR')
              target = target.parentNode;
            var idx = Number(target.getAttribute('data-index'));
            _ac_mouseover(idx);
        });
        var valCellEl = document.createElement('td');
        rowEl.appendChild(valCellEl);
        if (ac_completions[i].compSpan) {
          valCellEl.appendChild(ac_completions[i].compSpan);
        }
        var docCellEl = document.createElement('td');
        rowEl.appendChild(docCellEl);
        if (ac_completions[i].docSpan &&
            ac_completions[i].docSpan.textContent) {
          docCellEl.appendChild(document.createTextNode(' = '));
          docCellEl.appendChild(ac_completions[i].docSpan);
        }
      }
    }

    while (clist.childNodes.length) {
        clist.removeChild(clist.childNodes[0]);
    }
    clist.appendChild(tableEl);
    // position
    var inputBounds = nodeBounds(ac_focusedInput);
    clist.style.left = inputBounds.x + 'px';
    clist.style.top = (inputBounds.y + inputBounds.h) + 'px';

    // Note - we use '' instead of 'block', since 'block' has odd effects on
    // the screen in IE, and causes scrollbars to resize
    clist.style.display = '';

    window.setTimeout(ac_autoscroll, 100);

  } else {
    if (clist) {
      clist.style.display = 'none';
      while (clist.childNodes.length) {
          clist.removeChild(clist.childNodes[0]);
      }
    }
  }
}

// TODO(jrobbins): make arrow keys and mouse not conflict if they are
// used at the same time.


/** Scroll the autocomplete menu to show the currently selected row. */
function ac_autoscroll() {
  var acList = document.getElementById('ac-list');
  var acSelRow = document.getElementById('ac-selected-row');
  var acSelRowTop = acSelRow ? acSelRow.offsetTop : 0;
  var acSelRowHeight = acSelRow ? acSelRow.offsetHeight : 0;


  var EXTRA = 8;  // Go an extra few pixels so the next row is partly exposed.

  if (!acList || !acSelRow) return;

  // Autoscroll upward if the selected item is above the visible area,
  // else autoscroll downward if the selected item is below the visible area.
  if (acSelRowTop < acList.scrollTop) {
    acList.scrollTop = acSelRowTop - EXTRA;
  } else if (acSelRowTop + acSelRowHeight + EXTRA >
             acList.scrollTop + acList.offsetHeight) {
    acList.scrollTop = (acSelRowTop + acSelRowHeight -
                        acList.offsetHeight + EXTRA);
  }
}


/** the position of the text caret in the given text field.
 *
 * @param textField an INPUT node with type=text or a TEXTAREA node
 * @return an index in [0, textField.value.length]
 */
function ac_getCaretPosition_(textField) {
  if ('INPUT' == textField.tagName) {
    var caret = textField.value.length;

    // chrome/firefox
    if (undefined != textField.selectionStart) {
      caret = textField.selectionEnd;

      // JER: Special treatment for issue status field that makes all
      // options show up more often
      if (textField.id.startsWith('status')) {
        caret = textField.selectionStart;
      }
      // ie
    } else if (document.selection) {
      // get an empty selection range
      var range = document.selection.createRange();
      var origSelectionLength = range.text.length;
      // Force selection start to 0 position
      range.moveStart('character', -caret);
      // the caret end position is the new selection length
      caret = range.text.length;

      // JER: Special treatment for issue status field that makes all
      // options show up more often
      if (textField.id.startsWith('status')) {
        // The amount that the selection grew when we forced start to
        // position 0 is == the original start position.
        caret = range.text.length - origSelectionLength;
      }
    }

    return caret;
  } else {
    // a textarea

    return GetCursorPos(window, textField);
  }
}

/**
 * on key press, the keycode for comma comes out as 44.
 * on keydown it comes out as 188.
 */
var AC_COMMA_KEYCODE = ','.charCodeAt(0);

function BR_hasExcessBlurEvents() {
  return navigator.userAgent.toLowerCase().indexOf('webkit') != -1;
}

function BR_hasUnreliableMouseDown() {
  return navigator.userAgent.toLowerCase().indexOf('webkit') != -1;
}
