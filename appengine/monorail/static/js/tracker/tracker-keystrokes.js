/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * This file contains JS functions that implement keystroke accelerators
 * for Monorail.
 */

/**
 * Array of HTML elements where the kibbles cursor can be.  E.g.,
 * the TR elements of an issue list, or the TR's for comments on an issue.
 */
var TKR_cursorStops;

/**
 * Integer index into TKR_cursorStops of the currently selected cursor
 * stop, or undefined if nothing has been selected yet.
 */
var TKR_selected = undefined;


/**
 * Scroll to the issue search field, set keyboard focus there, and
 * select all of its text contents.  We use <span id="qq"> around
 * that form field because IE has a broken getElementById that
 * confuses id with form element names.  We do this in a setTimeout()
 * so that the keystroke that triggers it ('/') will not be typed into
 * the search box itself.
 */
function TKR_focusArtifactSearchField() {
  var el = TKR_getArtifactSearchField();
  el.focus();  // forces browser to scroll to make field visible.
  el.select();
}


/**
 * Always hide the keystroke help overlay, if it has been loaded.
 */
function TKR_closeKeystrokeHelp() {
  var dialog = document.getElementById('keys_help');
  if (dialog) {
    dialog.style.display = 'none';
  }
}

/**
 * Show or hide the keystroke help overlay.  If it has not been loaded
 * yet, make the request to load it.
 */
function TKR_toggleKeystrokeHelp() {
  var dialog = document.getElementById('keys_help');
  if (dialog) {
    dialog.style.display = dialog.style.display ? '' : 'none';
  } else {
   TKR_buildKeystrokeHelp();
  }
}

function TKR_createChild(parentEl, tag, optClassName, optID, optText, optStyle) {
    var el = document.createElement(tag);
    if (optClassName) el.classList.add(optClassName);
    if (optID) el.id = optID;
    if (optText) el.textContent = optText;
    if (optStyle) el.setAttribute('style', optStyle);
    parentEl.appendChild(el);
    return el;
}

function TKR_createKeysHelpHeader(row, text) {
    TKR_createChild(row, 'td');
    TKR_createChild(row, 'th', null, null, text);
    return row;
}

function TKR_createKeysHelpItem(row, key1, key2, doc) {
    var keyCell = TKR_createChild(row, 'td', 'shortcut');
    TKR_createChild(keyCell, 'span', 'keystroke', null, key1);
    if (key2) {
        keyCell.appendChild(document.createTextNode(' / '));
        TKR_createChild(keyCell, 'span', 'keystroke', null, key2);
    }
    TKR_createChild(keyCell, 'b', null, null, ' :');

    TKR_createChild(row, 'td', null, null, doc);
    return keyCell;
}

/**
 * Build the keystroke help dialog.  It is not part of the template because it
 * not used on the vast majority of pages viewed.
 */
function TKR_buildKeystrokeHelp() {
   var helpArea = document.getElementById('helparea');
   var dialog = TKR_createChild(
       helpArea, 'div', 'fullscreen-popup', 'keys_help');
   var closeX = TKR_createChild(
       dialog, 'a', null, null, 'Close', 'float:right; font-size:140%');
   closeX.href = '#';
   closeX.addEventListener('click', function () {
           $('keys_help').style.display = 'none';
       });
   TKR_createChild(
       dialog, 'div', null, null, 'Issue tracker keyboard shortcuts',
       'font-size: 140%');
   TKR_createChild(dialog, 'hr');

   var keysTable = TKR_createChild(
       dialog, 'table', null, null, null, 'width: 100%');
   var headerRow = TKR_createChild(keysTable, 'tr');
   TKR_createKeysHelpHeader(headerRow, 'Issue list');
   TKR_createKeysHelpHeader(headerRow, 'Issue details');
   TKR_createKeysHelpHeader(headerRow, 'Anywhere')
   var row1 = TKR_createChild(keysTable, 'tr');
   TKR_createKeysHelpItem(row1, 'k', 'j', 'up/down in the list');
   TKR_createKeysHelpItem(row1, 'k', 'j', 'prev/next issue in list');
   TKR_createKeysHelpItem(row1, '/', null, 'focus on the issue search field');
   var row2 = TKR_createChild(keysTable, 'tr');
   TKR_createKeysHelpItem(row2, 'o', '<Enter>', 'open the current issue');
   TKR_createKeysHelpItem(row2, 'u', null, 'up to issue list');
   TKR_createKeysHelpItem(row2, 'c', null, 'compose a new issue');
   var row3 = TKR_createChild(keysTable, 'tr');
   TKR_createKeysHelpItem(row3, 'Shift-O', null, 'open issue in new tab');
   TKR_createKeysHelpItem(row3, 'p', 'n', 'prev/next comment');
   TKR_createKeysHelpItem(row3, 's', null, 'star the current issue');
   var row4 = TKR_createChild(keysTable, 'tr');
   TKR_createKeysHelpItem(row4, 'x', null, 'select the current issue');
   TKR_createKeysHelpItem(row4, 'r', null, 'add comment & make changes');
   TKR_createKeysHelpItem(row4, '?', null, 'show this help dialog');

   var footer = TKR_createChild(
       dialog, 'div', null, null, null,
       'font-weight:normal; margin-top: 3em;');
   TKR_createChild(footer, 'hr');
   TKR_createChild(footer, 'div', null, null,
       ('Note: Only signed in users can star issues or add comments, ' +
        'and only project members can select issues for bulk edits.'));
}


/**
 * Register keystrokes that apply to all pages in the current component.
 * E.g., keystrokes that should work on every page under the "Issues" tab.
 * @param {string} listUrl Rooted URL of the artifact list.
 * @param {string} entryUrl Rooted URL of the artifact entry page.
 * @param {string} currentPageType One of 'list', 'entry', or 'detail'.
 */
function TKR_setupKibblesComponentKeys(listUrl, entryUrl, currentPageType) {
  kibbles.keys.addKeyPressListener(
     '/',
     function() {
       window.setTimeout(TKR_focusArtifactSearchField, 10);
     });
  if (currentPageType != 'entry') {
    kibbles.keys.addKeyPressListener(
       'c', function() { TKR_go(entryUrl); });
  }
  if (currentPageType != 'list') {
    kibbles.keys.addKeyPressListener(
       'u', function() { TKR_go(listUrl); });
  }
  kibbles.keys.addKeyPressListener('?', TKR_toggleKeystrokeHelp);

  kibbles.keys.addKeyPressListener('ESC', TKR_closeKeystrokeHelp);
}


/**
 * On the artifact list page, go to the artifact at the kibbles cursor.
 * @param {number} linkCellIndex row child that is expected to hold a link.
 */
function TKR_openArtifactAtCursor(linkCellIndex, newWindow) {
  if (TKR_selected >= 0 && TKR_selected < TKR_cursorStops.length) {
    window._goIssue(TKR_selected, newWindow);
  }
}


/**
 * On the artifact list page, toggle the checkbox for the artifact at
 * the kibbles cursor.
 * @param {number} cbCellIndex row child that is expected to hold a checkbox.
 */
function TKR_selectArtifactAtCursor(cbCellIndex) {
  if (TKR_selected >= 0 && TKR_selected < TKR_cursorStops.length) {
    var cell = TKR_cursorStops[TKR_selected].children[cbCellIndex];
    var cb = cell.firstChild;
    while (cb && cb.tagName != 'INPUT') {
      cb = cb.nextSibling;
    }
    if (cb) {
      cb.checked = cb.checked ? '' : 'checked';
      TKR_highlightRow(cb);
    }
  }
}

/**
 * On the artifact list page, toggle the star for the artifact at
 * the kibbles cursor.
 * @param {number} cbCellIndex row child that is expected to hold a checkbox
 *     and star widget.
 * @param {string} set_star_token The security token.
 */
function TKR_toggleStarArtifactAtCursor(cbCellIndex, set_star_token) {
  if (TKR_selected >= 0 && TKR_selected < TKR_cursorStops.length) {
    var cell = TKR_cursorStops[TKR_selected].children[cbCellIndex];
    var starIcon = cell.firstChild;
    while (starIcon && starIcon.tagName != 'A') {
      starIcon = starIcon.nextSibling;
    }
    if (starIcon) {
      _TKR_toggleStar(
          starIcon, issueRefs[TKR_selected]['project_name'],
          issueRefs[TKR_selected]['id'], null, null, set_star_token);
    }
  }
}

/**
 * Updates the style on new stop and clears the style on the former stop.
 * @param {Object} newStop the cursor stop that the user is selecting now.
 * @param {Object} formerStop the old cursor stop, if any.
 */
function TKR_updateCursor(newStop, formerStop) {
  TKR_selected = undefined;
  if (formerStop) {
    formerStop.element.classList.remove('cursor_on');
    formerStop.element.classList.add('cursor_off');
  }
  if (newStop && newStop.element) {
    newStop.element.classList.remove('cursor_off');
    newStop.element.classList.add('cursor_on');
    TKR_selected = newStop.index;
  }
}


/**
 * Walk part of the page DOM to find elements that should be kibbles
 * cursor stops.  E.g., the rows of the issue list results table.
 * @return {Array} an array of html elements.
 */
function TKR_findCursorRows() {
  var rows = [];
  var cursorarea = document.getElementById('cursorarea');
  TKR_accumulateCursorRows(cursorarea, rows);
  return rows;
}


/**
 * Recusrively walk part of the page DOM to find elements that should
 * be kibbles cursor stops.  E.g., the rows of the issue list results
 * table.  The cursor stops are appended to the given rows array.
 * @param {Element} parent html element to start on.
 * @param {Array} rows  array of html TR or DIV elements, each cursor stop will
 *    be added to this array.
 */
function TKR_accumulateCursorRows(parent, rows) {
  for (var i = 0; i < parent.childNodes.length; i++) {
    var elem = parent.childNodes[i];
    var name = elem.tagName;
    if (name && (name == 'TR' || name == 'DIV')) {
      if (elem.className.indexOf('cursor') >= 0) {
        elem.cursorIndex = rows.length;
        rows.push(elem);
      }
    }
    TKR_accumulateCursorRows(elem, rows);
  }
}


/**
 * Initialize kibbles cursors stops for the current page.
 * @param {boolean} selectFirstStop True if the first stop should be
 *   selected before the user presses any keys.
 */
function TKR_setupKibblesCursorStops(selectFirstStop) {
  kibbles.skipper.addStopListener(
      kibbles.skipper.LISTENER_TYPE.PRE, TKR_updateCursor);

  // Set the 'offset' option to return the middle of the client area
  // an option can be a static value, or a callback
  kibbles.skipper.setOption('padding_top', 50);

  // Set the 'offset' option to return the middle of the client area
  // an option can be a static value, or a callback
  kibbles.skipper.setOption('padding_bottom', 50);

  // register our stops with skipper
  TKR_cursorStops = TKR_findCursorRows();
  for (var i = 0; i < TKR_cursorStops.length; i++) {
    var element = TKR_cursorStops[i];
    kibbles.skipper.append(element);

    if (element.className.indexOf('cursor_on') >= 0) {
      kibbles.skipper.setCurrentStop(i);
    }
  }
}


/**
 * Initialize kibbles keystrokes for an artifact entry page.
 * @param {string} listUrl Rooted URL of the artifact list.
 * @param {string} entryUrl Rooted URL of the artifact entry page.
 */
function TKR_setupKibblesOnEntryPage(listUrl, entryUrl) {
  TKR_setupKibblesComponentKeys(listUrl, entryUrl, 'entry');
}


/**
 * Initialize kibbles keystrokes for an artifact list page.
 * @param {string} listUrl Rooted URL of the artifact list.
 * @param {string} entryUrl Rooted URL of the artifact entry page.
 * @param {string} projectName Name of the current project.
 * @param {number} linkCellIndex table column that is expected to
 *   link to individual artifacts.
 * @param {number} opt_checkboxCellIndex table column that is expected
 *   to contain a selection checkbox.
 * @param {string} set_star_token The security token.
 */
function TKR_setupKibblesOnListPage(
    listUrl, entryUrl, projectName, linkCellIndex,
    opt_checkboxCellIndex, set_star_token) {
  TKR_setupKibblesCursorStops(true);

  kibbles.skipper.addFwdKey('j');
  kibbles.skipper.addRevKey('k');

  if (opt_checkboxCellIndex != undefined) {
    var cbCellIndex = opt_checkboxCellIndex;
    kibbles.keys.addKeyPressListener(
        'x', function() { TKR_selectArtifactAtCursor(cbCellIndex); });
    kibbles.keys.addKeyPressListener(
        's',
         function() {
           TKR_toggleStarArtifactAtCursor(cbCellIndex, set_star_token);
         });
  }
  kibbles.keys.addKeyPressListener(
      'o', function() { TKR_openArtifactAtCursor(linkCellIndex, false); });
  kibbles.keys.addKeyPressListener(
      'O', function() { TKR_openArtifactAtCursor(linkCellIndex, true); });
  kibbles.keys.addKeyPressListener(
      'enter', function() { TKR_openArtifactAtCursor(linkCellIndex); });

  TKR_setupKibblesComponentKeys(listUrl, entryUrl, 'list');
}


/**
 * Initialize kibbles keystrokes for an artifact detail page.
 * @param {string} listUrl Rooted URL of the artifact list.
 * @param {string} entryUrl Rooted URL of the artifact entry page.
 * @param {string} prevUrl Rooted URL of previous artifact in list.
 * @param {string} nextUrl Rooted URL of next artifact in list.
 * @param {string} projectName name of the current project.
 * @param {boolean} userCanComment True if the user may add a comment.
 * @param {boolean} userCanStar True if the user may add a star.
 * @param {string} set_star_token The security token.
 */
function TKR_setupKibblesOnDetailPage(
    listUrl, entryUrl, prevUrl, nextUrl, projectName, localId,
    userCanComment, userCanStar, set_star_token) {
  TKR_setupKibblesCursorStops(false);
  kibbles.skipper.addFwdKey('n');
  kibbles.skipper.addRevKey('p');
  if (prevUrl) {
    kibbles.keys.addKeyPressListener(
      'k', function() { TKR_go(prevUrl); });
  }
  if (nextUrl) {
    kibbles.keys.addKeyPressListener(
      'j', function() { TKR_go(nextUrl); });
  }
  if (userCanComment) {
    kibbles.keys.addKeyPressListener(
       'r',
       function() {
         window.setTimeout(TKR_openIssueUpdateForm, 10);
       });
  }
  if (userCanStar) {
    kibbles.keys.addKeyPressListener(
        's',
         function() {
           var star = document.getElementById('star');
           TKR_toggleStar(star, projectName, localId, null, null, set_star_token);
           TKR_syncStarIcons(star, 'star2');
         });
  }
  TKR_setupKibblesComponentKeys(listUrl, entryUrl, 'detail');
}
