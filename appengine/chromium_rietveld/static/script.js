// Copyright 2008 Google Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Generic helpers

/**
 * Create a new XMLHttpRequest in a cross-browser-compatible way.
 * @return XMLHttpRequest object
 */
function M_getXMLHttpRequest() {
  try {
    return new XMLHttpRequest();
  } catch (e) { }

  try {
    return new ActiveXObject("Msxml2.XMLHTTP");
  } catch (e) { }

  try {
    return new ActiveXObject("Microsoft.XMLHTTP");
  } catch (e) { }

  return null;
}

/**
 * Finds the element's parent in the DOM tree.
 * @param {Element} element The element whose parent we want to find
 * @return The parent element of the given element
 */
function M_getParent(element) {
  if (element.parentNode) {
    return element.parentNode;
  } else if (element.parentElement) {
    // IE compatibility. Why follow standards when you can make up your own?
    return element.parentElement;
  }
  return null;
}

/**
 * Finds the event's target in a way that works on all browsers.
 * @param {Event} e The event object whose target we want to find
 * @return The element receiving the event
 */
function M_getEventTarget(e) {
  var src = e.srcElement ? e.srcElement : e.target;
  return src;
}

/**
 * Function to determine if we are in a KHTML-based browser(Konq/Safari).
 * @return Boolean of whether we are in a KHTML browser
 */
function M_isKHTML() {
  var agt = navigator.userAgent.toLowerCase();
  return (agt.indexOf("safari") != -1) || (agt.indexOf("khtml") != -1);
}

/**
 * Function to determine if we are running in an IE browser.
 * @return Boolean of whether we are running in IE
 */
function M_isIE() {
  return (navigator.userAgent.toLowerCase().indexOf("msie") != -1) &&
         !window.opera;
}

/**
 * Function to determine if we are in a WebKit-based browser (Chrome/Safari).
 * @return Boolean of whether we are in a WebKit browser
 */
function M_isWebKit() {
  return navigator.userAgent.toLowerCase().indexOf("webkit") != -1;
}

/**
 * Stop the event bubbling in a browser-independent way. Sometimes required
 * when it is not easy to return true when an event is handled.
 * @param {Window} win The window in which this event is happening
 * @param {Event} e The event that we want to cancel
 */
function M_stopBubble(win, e) {
  if (!e) {
    e = win.event;
  }
  e.cancelBubble = true;
  if (e.stopPropagation) {
    e.stopPropagation();
  }
}

/**
 * Return distance in pixels from the top of the document to the given element.
 * @param {Element} element The element whose offset we want to find
 * @return Integer value of the height of the element from the top
 */
function M_getPageOffsetTop(element) {
  var y = element.offsetTop;
  if (element.offsetParent != null) {
    y += M_getPageOffsetTop(element.offsetParent);
  }
  return y;
}

/**
 * Return distance in pixels of the given element from the left of the document.
 * @param {Element} element The element whose offset we want to find
 * @return Integer value of the horizontal position of the element
 */
function M_getPageOffsetLeft(element) {
  var x = element.offsetLeft;
  if (element.offsetParent != null) {
    x += M_getPageOffsetLeft(element.offsetParent);
  }
  return x;
}

/**
 * Find the height of the window viewport.
 * @param {Window} win The window whose viewport we would like to measure
 * @return Integer value of the height of the given window
 */
function M_getWindowHeight(win) {
  return M_getWindowPropertyByBrowser_(win, M_getWindowHeightGetters_);
}

/**
 * Find the vertical scroll position of the given window.
 * @param {Window} win The window whose scroll position we want to find
 * @return Integer value of the scroll position of the given window
 */
function M_getScrollTop(win) {
  return M_getWindowPropertyByBrowser_(win, M_getScrollTopGetters_);
}

/**
 * Scroll the target element into view at 1/3rd of the window height only if
 * the scrolling direction matches the direction that was asked for.
 * @param {Window} win The window in which the element resides
 * @param {Element} element The element that we want to bring into view
 * @param {Integer} direction Positive for scroll down, negative for scroll up
 */
function M_scrollIntoView(win, element, direction) {
  var elTop = M_getPageOffsetTop(element);
  var winHeight = M_getWindowHeight(win);
  var targetScroll = elTop - winHeight / 3;
  var scrollTop = M_getScrollTop(win);

  if ((direction > 0 && scrollTop < targetScroll) ||
      (direction < 0 && scrollTop > targetScroll)) {
    win.scrollTo(M_getPageOffsetLeft(element), targetScroll);
  }
}

/**
 * Returns whether the element is visible.
 * @param {Window} win The window that the element resides in
 * @param {Element} element The element whose visibility we want to determine
 * @return Boolean of whether the element is visible in the window or not
 */
function M_isElementVisible(win, element) {
  var elTop = M_getPageOffsetTop(element);
  var winHeight = M_getWindowHeight(win);
  var winTop = M_getScrollTop(win);
  if (elTop < winTop || elTop > winTop + winHeight) {
    return false;
  }
  return true;
}

// Cross-browser compatibility quirks and methodology borrowed from
// common.js

var M_getWindowHeightGetters_ = {
  ieQuirks_: function(win) {
    return win.document.body.clientHeight;
  },
  ieStandards_: function(win) {
    return win.document.documentElement.clientHeight;
  },
  dom_: function(win) {
    return win.innerHeight;
  }
};

var M_getScrollTopGetters_ = {
  ieQuirks_: function(win) {
    return win.document.body.scrollTop;
  },
  ieStandards_: function(win) {
    return win.document.documentElement.scrollTop;
  },
  dom_: function(win) {
    return win.pageYOffset;
  }
};

/**
 * Slightly modified from common.js: Konqueror has the CSS1Compat property
 * but requires the standard DOM functionlity, not the IE one.
 */
function M_getWindowPropertyByBrowser_(win, getters) {
  try {
    if (!M_isKHTML() && "compatMode" in win.document &&
        win.document.compatMode == "CSS1Compat") {
      return getters.ieStandards_(win);
    } else if (M_isIE()) {
      return getters.ieQuirks_(win);
    }
  } catch (e) {
    // Ignore for now and fall back to DOM method
  }

  return getters.dom_(win);
}

// Global search box magic (global.html)

/**
 * Handle the onblur action of the search box, replacing it with greyed out
 * instruction text when it is empty.
 * @param {Element} element The search box element
 */
function M_onSearchBlur(element) {
  var defaultMsg = "Enter a changelist#, user, or group";
  if (element.value.length == 0 || element.value == defaultMsg) {
    element.style.color = "gray";
    element.value = defaultMsg;
  } else {
    element.style.color = "";
  }
}

/**
 * Handle the onfocus action of the search box, emptying it out if no new text
 * was entered.
 * @param {Element} element The search box element
 */
function M_onSearchFocus(element) {
  if (element.style.color == "gray") {
    element.style.color = "";
    element.value = "";
  }
}

// Inline diffs (changelist.html)

/**
 * Creates an iframe to load the diff in the background and when that's done,
 * calls a function to transfer the contents of the iframe into the current DOM.
 * @param {Integer} suffix The number associated with that diff
 * @param {String} url The URL that the diff should be fetched from
 * @return false (for event bubbling purposes)
 */
function M_showInlineDiff(suffix, url) {
  var hide = document.getElementById("hide-" + suffix);
  var show = document.getElementById("show-" + suffix);
  var frameDiv = document.getElementById("frameDiv-" + suffix);
  var dumpDiv = document.getElementById("dumpDiv-" + suffix);
  var diffTR = document.getElementById("diffTR-" + suffix);
  var hideAll = document.getElementById("hide-alldiffs");
  var showAll = document.getElementById("show-alldiffs");

  /* Twiddle the "show/hide all diffs" link */
  if (hide.style.display != "") {
    M_CL_hiddenInlineDiffCount -= 1;
    if (M_CL_hiddenInlineDiffCount == M_CL_maxHiddenInlineDiffCount) {
      showAll.style.display = "inline";
      hideAll.style.display = "none";
    } else {
      showAll.style.display = "none";
      hideAll.style.display = "inline";
    }
  }

  hide.style.display = "";
  show.style.display = "none";
  dumpDiv.style.display = "block"; // XXX why not ""?
  diffTR.style.display = "";
  if (!frameDiv.innerHTML) {
    if (M_isKHTML()) {
      frameDiv.style.display = "block"; // XXX why not ""?
    }
    frameDiv.innerHTML = "<iframe src='" + url + "'" +
    " onload='M_dumpInlineDiffContent(this, \"" + suffix + "\")'"+
    "height=1>your browser does not support iframes!</iframe>";
  }
  return false;
}

/**
 * Hides the diff that was retrieved with M_showInlineDiff.
 * @param {Integer} suffix The number associated with the diff we want to hide
 */
function M_hideInlineDiff(suffix) {
  var hide = document.getElementById("hide-" + suffix);
  var show = document.getElementById("show-" + suffix);
  var dumpDiv = document.getElementById("dumpDiv-" + suffix);
  var diffTR = document.getElementById("diffTR-" + suffix);
  var hideAll = document.getElementById("hide-alldiffs");
  var showAll = document.getElementById("show-alldiffs");

  /* Twiddle the "show/hide all diffs" link */
  if (hide.style.display != "none") {
    M_CL_hiddenInlineDiffCount += 1;
    if (M_CL_hiddenInlineDiffCount == M_CL_maxHiddenInlineDiffCount) {
      showAll.style.display = "inline";
      hideAll.style.display = "none";
    } else {
      showAll.style.display = "none";
      hideAll.style.display = "inline";
    }
  }

  hide.style.display = "none";
  show.style.display = "inline";
  diffTR.style.display = "none";
  dumpDiv.style.display = "none";
  return false;
}

/**
 * Dumps the content of the given iframe into the appropriate div in order
 * for the diff to be displayed.
 * @param {Element} iframe The IFRAME that contains the diff data
 * @param {Integer} suffix The number associated with the diff
 */
function M_dumpInlineDiffContent(iframe, suffix) {
  var dumpDiv = document.getElementById("dumpDiv-" + suffix);
  dumpDiv.style.display = "block"; // XXX why not ""?
  dumpDiv.innerHTML = iframe.contentWindow.document.body.innerHTML;
  // TODO: The following should work on all browsers instead of the
  // innerHTML hack above. At this point I don't remember what the exact
  // problem was, but it didn't work for some reason.
  // dumpDiv.appendChild(iframe.contentWindow.document.body);
  if (M_isKHTML()) {
    var frameDiv = document.getElementById("frameDiv-" + suffix);
    frameDiv.style.display = "none";
  }
}

/**
 * Goes through all the diffs and triggers the onclick action on them which
 * should start the mechanism for displaying them.
 * @param {Integer} num The number of diffs to display (0-indexed)
 */
function M_showAllDiffs(num) {
  for (var i = 0; i < num; i++) {
    var link = document.getElementById('show-' + i);
    // Since the user may not have JS, the template only shows the diff inline
    // for the onclick action, not the href. In order to activate it, we must
    // call the link's onclick action.
    if (link.className.indexOf("reverted") == -1) {
      link.onclick();
    }
  }
}

/**
 * Goes through all the diffs and hides them by triggering the hide link.
 * @param {Integer} num The number of diffs to hide (0-indexed)
 */
function M_hideAllDiffs(num) {
  for (var i = 0; i < num; i++) {
    var link = document.getElementById('hide-' + i);
    // If the user tries to hide, that means they have JS, which in turn means
    // that we can just set href in the href of the hide link.
    link.onclick();
  }
}

// Inline comment submission forms (changelist.html, file.html)

/**
 * Changes the elements display style to "" which renders it visible.
 * @param {String|Element} elt The id of the element or the element itself
 */
function M_showElement(elt) {
  if (typeof elt == "string") {
    elt = document.getElementById(elt);
  }
  if (elt) elt.style.display = "";
}

/**
 * Changes the elements display style to "none" which renders it invisible.
 * @param {String|Element} elt The id of the element or the element itself
 */
function M_hideElement(elt) {
  if (typeof elt == "string") {
    elt = document.getElementById(elt);
  }
  if (elt) elt.style.display = "none";
}

/**
 * Toggle the visibility of a section. The little indicator triangle will also
 * be toggled.
 * @param {String} id The id of the target element
 */
function M_toggleSection(id) {
  var sectionStyle = document.getElementById(id).style;
  var pointerStyle = document.getElementById(id + "-pointer").style;

  if (sectionStyle.display == "none") {
    sectionStyle.display = "";
    pointerStyle.backgroundImage = "url('" + media_url + "opentriangle.gif')";
  } else {
    sectionStyle.display = "none";
    pointerStyle.backgroundImage = "url('" + media_url + "closedtriangle.gif')";
  }
}


/**
 * Callback for XMLHttpRequest.
 */
function M_PatchSetFetched() {
  if (http_request.readyState != 4)
    return;

  var section = document.getElementById(http_request.div_id);
  if (http_request.status == 200) {
    section.innerHTML = http_request.responseText;
    /* initialize dashboardState again to update cached patch rows */
    if (dashboardState) dashboardState.initialize();
  } else {
    section.innerHTML =
        '<div style="color:red">Could not load the patchset (' +
        http_request.status + ').</div>';
  }
}

/**
 * Toggle the visibility of a patchset, and fetches it if necessary.
 * @param {String} issue The issue key
 * @param {String} id The patchset key
 */
function M_toggleSectionForPS(issue, patchset) {
  var id = 'ps-' + patchset;
  M_toggleSection(id);
  var section = document.getElementById(id);
  if (section.innerHTML.search("<div") != -1)
    return;

  section.innerHTML = "<div>Loading...</div>"
  http_request = M_getXMLHttpRequest();
  if (!http_request)
    return;

  http_request.open('GET', base_url + issue + "/patchset/" + patchset, true);
  http_request.onreadystatechange = M_PatchSetFetched;
  http_request.div_id = id;
  http_request.send(null);
}

/**
 * Toggle the visibility of the revert reason popup.
 */
function M_toggleRevertReasonPopup(display) {
  var popupElement = document.getElementById("revert-reason-popup-div");
  // Remove all text from the textarea while toggling.
  document.getElementById("revert_reason_textarea").value = ""
  popupElement.style.display = display ? "" : "none";
}

/**
 * Validates the revert reason and submits the revert form.
 */
function M_createRevertPatchset() {
  revert_reason = document.getElementById("revert_reason_textarea").value;
  // Validate that the revert reason is not null and does not contain only
  // newlines and whitespace characters.
  if (revert_reason == null ||
      revert_reason.replace(/(\s+|\r\n|\n|\r)/gm, "") == "") {
    alert('Must enter a revert reason. Please try again.');
    return false;
  }

  document.getElementById("revert-form")["revert_reason"].value = revert_reason;

  check_cq_value = document.getElementById("check_cq").checked ? '1' : '0';
  document.getElementById("revert-form")["revert_cq"].value = check_cq_value;

  // Confirm that this patchset should really be reverted.
  return confirm("Proceed with creating a revert of this patchset?");
}

/**
 * Show or hide older try bot results.
 * @param {String} id The id of the div elements that holds all the try job
 *     a elements.
 * @param makeVisible If true, makes older try bots visible.
 */
function M_showTryJobResult(id, makeVisible) {
  // This set keeps track of the first occurance of each try job result for
  // a given builder.  The try job results are ordered reverse chronologically,
  // so we visit them from newest to oldest.
  var firstBuilderSet = {};
  var oldBuildersExist = false;
  jQuery('a', document.getElementById(id)).each(function(i) {
    var self = jQuery(this);
    var builder = self.text();
    if (self.attr('category') != 'cq_experimental')
    {
      if (self.attr('status') == 'try-pending') {
        // Try pending jobs are always visible.
        self.css('display', 'inline');
      } else if (builder in firstBuilderSet) {
        // This is not the first time we see this builder, so toggle its
        // visibility.
        self.css('display', makeVisible ? 'inline' : 'none');
        oldBuildersExist = true;
      } else {
        // The first time we see a builder, its always visible.  Remember the
        // builder name.
        self.css('display', 'inline');
        firstBuilderSet[builder] = true;
      }
    }
  });

  jQuery('#' + id + '-morelink')
    .css('display', !oldBuildersExist || makeVisible ? 'none' : '');
  jQuery('#' + id + '-lesslink')
    .css('display', oldBuildersExist && makeVisible ? '' : 'none');
}

/**
 * Toggle the visibility of the "Quick LGTM" link on the changelist page.
 * @param {String} id The id of the target element
 */
function M_toggleQuickLGTM(id) {
  M_toggleSection(id);
  window.scrollTo(0, document.body.offsetHeight);
}

// Comment expand/collapse

/**
 * Toggles whether the specified changelist comment is expanded/collapsed.
 * @param {Integer} cid The comment id, 0-indexed
 */
function M_switchChangelistComment(cid) {
  M_switchCommentCommon_('cl', String(cid));
}

/**
 * Toggles a comment or patchset.
 *
 * If the anchor has the form "#msgNUMBER" a message is toggled.
 * If the anchor has the form "#psNUMBER" a patchset is toggled.
 */
function M_toggleIssueOverviewByAnchor() {
  var href = window.location.href;
  var idx_hash = href.lastIndexOf('#');
  if (idx_hash != -1) {
    var anchor = href.slice(idx_hash+1, href.length);
    if (anchor.slice(0, 3) == 'msg') {
      var elem = document.getElementById(anchor);
      elem.className += ' referenced';
      var num = elem.getAttribute('name');
      if (anchor.slice(3) != lastMsgID)
        M_switchChangelistComment(num);
    } else if (anchor.slice(0, 2) == 'ps') {
      // hide last patchset which is visible by default.
      M_toggleSectionForPS(issueId, lastPSId);
      M_toggleSectionForPS(issueId, anchor.slice(2, anchor.length));
    }
  }
}

/**
 * Toggles whether the specified inline comment is expanded/collapsed.
 * @param {Integer} cid The comment id, 0-indexed
 * @param {Integer} lineno The lineno associated with the comment
 * @param {String} side The side (a/b) associated with the comment
 */
function M_switchInlineComment(cid, lineno, side) {
  M_switchCommentCommon_('inline', String(cid) + "-" + lineno + "-" + side);
}

/**
 * Used to expand all visible comments, hiding the preview and showing the
 * comment.
 * @param {String} prefix The level of the comment -- one of
 *                        ('cl', 'file', 'inline')
 * @param {Integer} num_comments The number of comments to show
 */
function M_expandAllVisibleComments(prefix, num_comments) {
  for (var i = 0; i < num_comments; i++) {
    M_hideElement(prefix + "-preview-" + i);
    M_showElement(prefix + "-comment-" + i);
  }
}

/**
 * Used to collapse all visible comments, showing the preview and hiding the
 * comment.
 * @param {String} prefix The level of the comment -- one of
 *                        ('cl', 'file', 'inline')
 * @param {Integer} num_comments The number of comments to hide
 */
function M_collapseAllVisibleComments(prefix, num_comments) {
  for (var i = 0; i < num_comments; i++) {
    M_showElement(prefix + "-preview-" + i);
    M_hideElement(prefix + "-comment-" + i);
  }
}

/**
 * Used to show all auto_generated comments.
 * @param {Integer} num_comments The total number of comments to loop through
 */
function M_showGeneratedComments(num_comments) {
  for (var i = 0; i < num_comments; i++) {
    // The top level msg div starts at index 1.
    M_showElement("generated-msg" + (i+1));
  }
}

/**
 * Used to hide all auto_generated comments.
 * @param {Integer} num_comments The total number of comments to loop through
 */
function M_hideGeneratedComments(num_comments) {
  for (var i = 0; i < num_comments; i++) {
    // The top level msg div starts at index 1.
    M_hideElement("generated-msg" + (i+1));
  }
}

// Common methods for comment handling (changelist.html, file.html,
// comment_form.html)

/**
 * Toggles whether the specified comment is expanded/collapsed. Works in
 * the review form.
 * @param {String} prefix The prefix of the comment element name.
 * @param {String} suffix The suffix of the comment element name.
 */
function M_switchCommentCommon_(prefix, suffix) {
  prefix && (prefix +=  '-');
  suffix && (suffix =  '-' + suffix);
  var previewSpan = document.getElementById(prefix + 'preview' + suffix);
  var commentDiv = document.getElementById(prefix + 'comment' + suffix);
  if (!previewSpan || !commentDiv) {
    alert('Failed to find comment element: ' +
          prefix + 'comment' + suffix + '. Please send ' +
          'this message with the URL to the app owner');
    return;
  }
  if (previewSpan.style.display == 'none') {
    M_showElement(previewSpan);
    M_hideElement(commentDiv);
  } else {
    M_hideElement(previewSpan);
    M_showElement(commentDiv);
  }
}

/**
 * Expands all inline comments.
 */
function M_expandAllInlineComments() {
  M_showAllInlineComments();
  var comments = document.getElementsByName("inline-comment");
  var commentsLength = comments.length;
  for (var i = 0; i < commentsLength; i++) {
    comments[i].style.display = "";
  }
  var previews = document.getElementsByName("inline-preview");
  var previewsLength = previews.length;
  for (var i = 0; i < previewsLength; i++) {
    previews[i].style.display = "none";
  }
}

/**
 * Collapses all inline comments.
 */
function M_collapseAllInlineComments() {
  M_showAllInlineComments();
  var comments = document.getElementsByName("inline-comment");
  var commentsLength = comments.length;
  for (var i = 0; i < commentsLength; i++) {
    comments[i].style.display = "none";
  }
  var previews = document.getElementsByName("inline-preview");
  var previewsLength = previews.length;
  for (var i = 0; i < previewsLength; i++) {
    previews[i].style.display = "";
  }
}


// Inline comments (file.html)

/**
 * Helper method to assign an onclick handler to an inline '[+]' link.
 * @param {Element} form The form containing the resizer
 * @param {String} suffix The suffix of the comment form id: lineno-side
 */
function M_createResizer_(form, suffix) {
  if (!form.hasResizer) {
    var resizer = document.getElementById("resizer").cloneNode(true);
    resizer.onclick = function() {
      var form = document.getElementById("comment-form-" + suffix);
      if (!form) return;
      form.text.rows += 5;
      form.text.focus();
    };

    var elementsLength = form.elements.length;
    for (var i = 0; i < elementsLength; ++i) {
      var node = form.elements[i];
      if (node.nodeName == "TEXTAREA") {
        var parent = M_getParent(node);
        parent.insertBefore(resizer, node.nextSibling);
        resizer.style.display = "";
        form.hasResizer = true;
      }
    }
  }
}

/**
 * Like M_createResizer_(), but updates the form's first textarea field.
 * This is assumed not to be the last field.
 * @param {Element} form The form whose textarea field to update.
 */
function M_addTextResizer_(form) {
  if (M_isWebKit()) {
    return; // WebKit has its own resizer.
  }
  var elementsLength = form.elements.length;
  for (var i = 0; i < elementsLength; ++i) {
    var node = form.elements[i];
    if (node.nodeName == "TEXTAREA") {
      var parent = M_getParent(node);
      var resizer = document.getElementById("resizer").cloneNode(true);
      var next = node.nextSibling;
      parent.insertBefore(resizer, next);
      resizer.onclick = function() {
	node.rows += 5;
	node.focus();
      };
      resizer.style.display = "";
      if (next && next.className == "resizer") { // Remove old resizer.
	parent.removeChild(next);
      }
      break;
    }
  }
}

/**
 * Updates a comment tr's name, depending on whether there are now comments
 * in it or not. Also updates the hook cache if required. Assumes that the
 * given TR already has name == "hook" and only tries to remove it if all
 * are empty.
 * @param {Element} tr The TR containing the potential comments
 */
function M_updateRowHook(tr) {
  if (!(tr && tr.cells)) return;
  // If all of the TR's cells are empty, remove the hook name
  var i = 0;
  var numCells = tr.cells.length;
  for (i = 0; i < numCells; i++) {
    if (tr.cells[i].innerHTML != "") {
      break;
    }
  }
  if (i == numCells) {
    tr.setAttribute("name",  "");
    hookState.updateHooks();
  }
  hookState.gotoHook(0);
}

/**
 * Combines all the divs from a single comment (generated by multiple buckets)
 * and undoes the escaping work done by Django filters, and inserts the result
 * into a given textarea.
 * @param {Array} divs An array of div elements to be combined
 * @param {Element} text The textarea whose value needs to be updated
 */
function M_setValueFromDivs(divs, text) {
  var lines = [];
  var divsLength = divs.length;
  for (var i = 0; i < divsLength; i++) {
    lines = lines.concat(divs[i].innerHTML.split("\n"));
    // It's _fairly_ certain that the last line in the div will be
    // empty, based on how the template works. If the last line in the
    // array is empty, then ignore it.
    if (lines.length > 0 && lines[lines.length - 1] == "") {
      lines.length = lines.length - 1;
    }
  }
  for (var i = 0; i < lines.length; i++) {
    // Undo the <a> tags added by urlize and urlizetrunc
    lines[i] = lines[i].replace(/<a (.*?)href=[\'\"]([^\'\"]+?)[\'\"](.*?)>(.*?)<\/a>/ig, '$2');
    // Undo the escape Django filter
    lines[i] = lines[i].replace(/&gt;/ig, ">");
    lines[i] = lines[i].replace(/&lt;/ig, "<");
    lines[i] = lines[i].replace(/&quot;/ig, "\"");
    lines[i] = lines[i].replace(/&#39;/ig, "'");
    lines[i] = lines[i].replace(/&amp;/ig, "&"); // Must be last
    text.value += "> " + lines[i] + "\n";
  }
}

/**
 * Return the specified URL parameter.
 * @param {String} sParam The name of the parameter.
 */
function M_getUrlParameter(sParam) {
    var sPageURL = window.location.search.substring(1);
    var sURLVariables = sPageURL.split('&');
    for (var i = 0; i < sURLVariables.length; i++) {
        var sParameterName = sURLVariables[i].split('=');
        if (sParameterName[0] == sParam) {
            return sParameterName[1];
        }
    }
}

/**
 * Toggles whether we display quoted text or not, both for inline and regular
 * comments. Inline comments will have lineno and side defined.
 * @param {String} cid The comment number
 * @param {String} bid The bucket number in that comment
 * @param {String} lineno (optional) Line number of the comment
 * @param {String} side (optional) 'a' or 'b'
 */
function M_switchQuotedText(cid, bid, lineno, side) {
  var tmp = ""
  if (typeof lineno != 'undefined' && typeof side != 'undefined')
    tmp = "-" + lineno + "-" + side;
  var extra = cid + tmp + "-" + bid;
  var div = document.getElementById("comment-text-" + extra);
  var a = document.getElementById("comment-hide-link-" + extra);
  if (div.style.display == "none") {
    div.style.display = "";
    a.innerHTML = "Hide quoted text";
  } else {
    div.style.display = "none";
    a.innerHTML = "Show quoted text";
  }
  if (tmp != "") {
    hookState.gotoHook(0);
  }
}



/**
 * Makes all inline comments visible. This is the default view.
 */
function M_showAllInlineComments() {
  var hide_elements = document.getElementsByName("hide-all-inline");
  var show_elements = document.getElementsByName("show-all-inline");
  for (var i = 0; i < hide_elements.length; i++) {
    hide_elements[i].style.display = "";
  }
  var elements = document.getElementsByName("comment-border");
  var elementsLength = elements.length;
  for (var i = 0; i < elementsLength; i++) {
    var tr = M_getParent(M_getParent(elements[i]));
    tr.style.display = "";
    tr.name = "hook";
  }
  for (var i = 0; i < show_elements.length; i++) {
    show_elements[i].style.display = "none";
  }
  hookState.updateHooks();
}

/**
 * Hides all inline comments, to make code easier ot read.
 */
function M_hideAllInlineComments() {
  var hide_elements = document.getElementsByName("hide-all-inline");
  var show_elements = document.getElementsByName("show-all-inline");
  for (var i = 0; i < show_elements.length; i++) {
    show_elements[i].style.display = "";
  }
  var elements = document.getElementsByName("comment-border");
  var elementsLength = elements.length;
  for (var i = 0; i < elementsLength; i++) {
    var tr = M_getParent(M_getParent(elements[i]));
    tr.style.display = "none";
    tr.name = "";
  }
  for (var i = 0; i < hide_elements.length; i++) {
    hide_elements[i].style.display = "none";
  }
  hookState.updateHooks();
}

/**
 * Flips between making inline comments visible and invisible.
 */
function M_toggleAllInlineComments() {
  var show_elements = document.getElementsByName("show-all-inline");
  if (!show_elements) {
    return;
  }
  if (show_elements[0].style.display == "none") {
    M_hideAllInlineComments();
  } else {
    M_showAllInlineComments();
  }
}

/**
 * Navigates to the diff with the requested versions on left/right
 */
function M_navigateDiff(issueid, filename) {
  var left = document.getElementById('left').value;
  var right = document.getElementById('right').value;
  if (left == '-1') {
    window.location.href = base_url + issueid + '/diff/' + right + '/' + filename;
  } else {
    window.location.href = base_url + issueid + '/diff2/' + left + ':' + right + '/' + filename;
  }
}

// File view keyboard navigation

/**
 * M_HookState class. Keeps track of the current 'hook' that we are on and
 * responds to n/p/N/P events.
 * @param {Window} win The window that the table is in.
 * @constructor
 */
function M_HookState(win) {
  /**
   * -2 == top of page; -1 == diff; or index into hooks array
   * @type Integer
   */
  this.hookPos = -2;

  /**
   * A cache of visible table rows with tr.name == "hook"
   * @type Array
   */
  this.visibleHookCache = [];

  /**
   * The indicator element that we move around
   * @type Element
   */
  this.indicator = document.getElementById("hook-sel");

  /**
   * The element the indicator points to
   * @type Element
   */
  this.indicated_element = null;

  /**
   * Caches whether we are in an IE browser
   * @type Boolean
   */
  this.isIE = M_isIE();

  /**
   * The window that the table with the hooks is in
   * @type Window
   */
  this.win = win;
}

/**
 * Find all the hook locations in a browser-portable fashion, and store them
 * in a cache.
 * @return Array of TR elements.
 */
M_HookState.prototype.computeHooks_ = function() {
  var allHooks = null;
  if (this.isIE) {
    // IE only recognizes the 'name' attribute on tags that are supposed to
    // have one, such as... not TR.
    var tmpHooks = document.getElementsByTagName("TR");
    var tmpHooksLength = tmpHooks.length;
    allHooks = [];
    for (var i = 0; i < tmpHooksLength; i++) {
      if (tmpHooks[i].name == "hook") {
        allHooks.push(tmpHooks[i]);
      }
    }
  } else {
    allHooks = document.getElementsByName("hook");
  }
  var visibleHooks = [];
  var allHooksLength = allHooks.length;
  for (var i = 0; i < allHooksLength; i++) {
    var hook = allHooks[i];
    if (hook.style.display == "") {
      visibleHooks.push(hook);
    }
  }
  this.visibleHookCache = visibleHooks;
  return visibleHooks;
};

/**
 * Recompute all the hook positions, update the hookPos, and update the
 * indicator's position if necessary, but do not scroll.
 */
M_HookState.prototype.updateHooks = function() {
  var curHook = null;
  if (this.indicated_element != null) {
    curHook = this.indicated_element;
  } else if (this.hookPos >= 0 && this.hookPos < this.visibleHookCache.length) {
    curHook = this.visibleHookCache[this.hookPos];
  }
  this.computeHooks_();
  var newHookPos = -1;
  if (curHook != null) {
    for (var i = 0; i < this.visibleHookCache.length; i++) {
      if (this.visibleHookCache[i] == curHook) {
        newHookPos = i;
        break;
      }
    }
  }
  if (newHookPos != -1) {
    this.hookPos = newHookPos;
  }
  this.gotoHook(0);
};

/**
 * Update the indicator's position to be at the top of the table row.
 * @param {Element} tr The tr whose top the indicator will be lined up with.
 */
M_HookState.prototype.updateIndicator_ = function(tr) {
  // Find out where the table's top is, and add one so that when we align
  // the position indicator, it takes off 1px from one tr and 1px from another.
  // This must be computed every time since the top of the table may move due
  // to window resizing.
  var tableTop = M_getPageOffsetTop(document.getElementById("table-top")) + 1;

  this.indicator.style.top = String(M_getPageOffsetTop(tr) -
                                    tableTop) + "px";
  var totWidth = 0;
  var numCells = tr.cells.length;
  for (var i = 0; i < numCells; i++) {
    totWidth += tr.cells[i].clientWidth;
  }
  this.indicator.style.left = "0px";
  this.indicator.style.width = totWidth + "px";
  this.indicator.style.display = "";
  this.indicated_element = tr;
};

/**
 * Update the indicator's position, and potentially scroll to the proper
 * location. Computes the new position based on current scroll position, and
 * whether the previously selected hook was visible.
 * @param {Integer} direction Scroll direction: -1 for up only, 1 for down only,
 *                            0 for no scrolling.
 */
M_HookState.prototype.gotoHook = function(direction) {
  var hooks = this.visibleHookCache;

  // Hide the current selection image
  this.indicator.style.display = "none";
  this.indicated_element = null;

  // Add a border to all td's in the selected row
  if (this.hookPos < -1) {
    if (direction != 0) {
      window.scrollTo(0, 0);
    }
    this.hookPos = -2;
  } else if (this.hookPos == -1) {
    var diffs = document.getElementsByName("diffs");
    if (diffs && diffs.length >= 1) {
      diffs = diffs[0];
    }
    if (diffs && direction != 0) {
      window.scrollTo(0, M_getPageOffsetTop(diffs) || 0);
    }
    this.updateIndicator_(document.getElementById("thecode").rows[0]);
  } else {
    if (this.hookPos < hooks.length) {
      var hook = hooks[this.hookPos];
      for (var i = 0; i < hook.cells.length; i++) {
        var td = hook.cells[i];
        if (td.id != null && td.id != "") {
          if (direction != 0) {
            M_scrollIntoView(this.win, td, direction);
          }
          break;
        }
      }
      // Found one!
      this.updateIndicator_(hook);
    } else {
      if (direction != 0) {
        window.scrollTo(0, document.body.offsetHeight);
      }
      this.hookPos = hooks.length;
      var thecode = document.getElementById("thecode");
      this.updateIndicator_(thecode.rows[thecode.rows.length - 1]);
    }
  }
};


/**
 * Update the indicator and hook position by moving to the next/prev line.
 * If the target line doesn't have a hook marker, the marker is added.
 * @param {Integer} direction Scroll direction: -1 for up, 1 for down.
 */
M_HookState.prototype.gotoLine = function(direction) {
  var thecode = document.getElementById("thecode").rows;
  // find current hook and store visible code lines
  var currHook = this.indicated_element;
  var hookIdx = -1;
  var codeRows = new Array();
  for (var i=0; i < thecode.length; i++) {
    if (thecode[i].id.substr(0, 4) == "pair") {
      codeRows.push(thecode[i]);
      if (currHook && thecode[i].id == currHook.id) {
        hookIdx = codeRows.length - 1;
      }
    }
  }
  if (direction > 0) {
    if (hookIdx == -1 && this.hookPos == -2) {  // not on a hook yet
      this.incrementHook_(false);
      this.gotoHook(0);
      return;
    } else if (hookIdx == -1 && this.indicated_element.id == "codeBottom") {
      // about to move off the borders
      return;
    } else if (hookIdx == codeRows.length - 1) {  // last row
      window.scrollTo(0, document.body.offsetHeight);
      this.hookPos = this.visibleHookCache.length;
      this.updateIndicator_(thecode[thecode.length - 1]);
      return;
    } else {
      hookIdx = Math.min(hookIdx + 1, codeRows.length - 1);
    }
  } else {
    if (hookIdx == -1 && this.hookPos < 0) {  // going beyond the top
      return;
    } else if (hookIdx == -1) { // we are at the bottom line
      hookIdx = codeRows.length - 1;
    } else if (hookIdx == 0) {  // we are at the top
      this.hookPos = -1;
      this.indicated_element = null;
      this.gotoHook(-1);
      return;
    } else {
      hookIdx = Math.max(hookIdx - 1, 0);
    }
  }
  var tr = codeRows[hookIdx];
  if (tr) {
    this.updateIndicator_(tr);
    M_scrollIntoView(this.win, tr, direction);
  }
}


/**
 * Updates hookPos relative to indicated line.
 * @param {Array} hooks Hook array.
 * @param {Integer} direction Wether to look for the next or prev element.
 */
M_HookState.prototype.updateHookPosByIndicator_ = function(hooks, direction) {
  if (this.indicated_element == null) {
    return;
  } else if (this.indicated_element.getAttribute("name") == "hook") {
    // hookPos is alread a hook
    return;
  }
  var indicatorLine = parseInt(this.indicated_element.id.split("-")[1]);
  for (var i=0; i < hooks.length; i++) {
    if (hooks[i].id.substr(0, 4) == "pair" &&
        parseInt(hooks[i].id.split("-")[1]) > indicatorLine) {
      if (direction > 0) {
        this.hookPos = i - 1;
      } else {
        this.hookPos = i;
      }
      return;
    }
  }
}


/**
 * Set this.hookPos to the next desired hook.
 * @param {Boolean} findComment Whether to look only for comment hooks
 */
M_HookState.prototype.incrementHook_ = function(findComment) {
  var hooks = this.visibleHookCache;
  if (this.indicated_line) {
    this.hookPos = this.findClosestHookPos_(hooks);
  }
  if (findComment) {
    this.hookPos = Math.max(0, this.hookPos + 1);
    while (this.hookPos < hooks.length &&
           hooks[this.hookPos].className != "inline-comments") {
      this.hookPos++;
    }
  } else {
    this.hookPos = Math.min(hooks.length, this.hookPos + 1);
  }
};

/**
 * Set this.hookPos to the previous desired hook.
 * @param {Boolean} findComment Whether to look only for comment hooks
 */
M_HookState.prototype.decrementHook_ = function(findComment) {
  var hooks = this.visibleHookCache;
  if (findComment) {
    this.hookPos = Math.min(hooks.length - 1, this.hookPos - 1);
    while (this.hookPos >= 0 &&
           hooks[this.hookPos].className != "inline-comments") {
      this.hookPos--;
    }
  } else {
    this.hookPos = Math.max(-2, this.hookPos - 1);
  }
};

/**
 * Find the first document element in sorted array elts whose vertical position
 * is greater than the given height from the top of the document. Optionally
 * look only for comment elements.
 *
 * @param {Integer} height The height in pixels from the top
 * @param {Array.<Element>} elts Document elements
 * @param {Boolean} findComment Whether to look only for comment elements
 * @return {Integer} The index of such an element, or elts.length otherwise
 */
function M_findElementAfter_(height, elts, findComment) {
  for (var i = 0; i < elts.length; ++i) {
    if (M_getPageOffsetTop(elts[i]) > height) {
      if (!findComment || elts[i].className == "inline-comments") {
        return i;
      }
    }
  }
  return elts.length;
}

/**
 * Find the last document element in sorted array elts whose vertical position
 * is less than the given height from the top of the document. Optionally
 * look only for comment elements.
 *
 * @param {Integer} height The height in pixels from the top
 * @param {Array.<Element>} elts Document elements
 * @param {Boolean} findComment Whether to look only for comment elements
 * @return {Integer} The index of such an element, or -1 otherwise
 */
function M_findElementBefore_(height, elts, findComment) {
  for (var i = elts.length - 1; i >= 0; --i) {
    if (M_getPageOffsetTop(elts[i]) < height) {
      if (!findComment || elts[i].className == "inline-comments") {
        return i;
      }
    }
  }
  return -1;
}

/**
 * Move to the next hook indicator and scroll.
 * @param opt_findComment {Boolean} Whether to look only for comment hooks
 */
M_HookState.prototype.gotoNextHook = function(opt_findComment) {
  // If the current hook is not on the page, select the first hook that is
  // either on the screen or below.
  var hooks = this.visibleHookCache;
  this.updateHookPosByIndicator_(hooks, 1);
  var diffs = document.getElementsByName("diffs");
  var thecode = document.getElementById("thecode");
  var findComment = Boolean(opt_findComment);
  if (diffs && diffs.length >= 1) {
    diffs = diffs[0];
  }
  if (this.hookPos >= 0 && this.hookPos < hooks.length &&
      M_isElementVisible(this.win, hooks[this.hookPos].cells[0])) {
    this.incrementHook_(findComment);
  } else if (this.hookPos == -2 &&
             (M_isElementVisible(this.win, diffs) ||
              M_getScrollTop(this.win) < M_getPageOffsetTop(diffs))) {
    this.incrementHook_(findComment)
  } else if (this.hookPos < hooks.length || (this.hookPos >= hooks.length &&
             !M_isElementVisible(
               this.win, thecode.rows[thecode.rows.length - 1].cells[0]))) {
    var scrollTop = M_getScrollTop(this.win);
    this.hookPos = M_findElementAfter_(scrollTop, hooks, findComment);
  }
  this.gotoHook(1);
};

/**
 * Move to the previous hook indicator and scroll.
 * @param opt_findComment {Boolean} Whether to look only for comment hooks
 */
M_HookState.prototype.gotoPrevHook = function(opt_findComment) {
  // If the current hook is not on the page, select the last hook that is
  // above the bottom of the screen window.
  var hooks = this.visibleHookCache;
  this.updateHookPosByIndicator_(hooks, -1);
  var diffs = document.getElementsByName("diffs");
  var findComment = Boolean(opt_findComment);
  if (diffs && diffs.length >= 1) {
    diffs = diffs[0];
  }
  if (this.hookPos == 0 && findComment) {
    this.hookPos = -2;
  } else if (this.hookPos >= 0 && this.hookPos < hooks.length &&
      M_isElementVisible(this.win, hooks[this.hookPos].cells[0])) {
    this.decrementHook_(findComment);
  } else if (this.hookPos > hooks.length) {
    this.hookPos = hooks.length;
  } else if (this.hookPos == -1 && M_isElementVisible(this.win, diffs)) {
    this.decrementHook_(findComment);
  } else if (this.hookPos == -2 && M_getScrollTop(this.win) == 0) {
  } else {
    var scrollBot = M_getScrollTop(this.win) + M_getWindowHeight(this.win);
    this.hookPos = M_findElementBefore_(scrollBot, hooks, findComment);
  }
  // The top of the diffs table is irrelevant if we want comment hooks.
  if (findComment && this.hookPos <= -1) {
    this.hookPos = -2;
  }
  this.gotoHook(-1);
};

/**
 * Finds the list of comments attached to the current hook, if any.
 *
 * @param self The calling object.
 * @return The list of comment DOM elements.
 */
function M_findCommentsForCurrentHook_(self) {
  var hooks = self.visibleHookCache;
  var hasHook = (self.hookPos >= 0 && self.hookPos < hooks.length &&
		 M_isElementVisible(self.win, hooks[self.hookPos].cells[0]));
  if (!hasHook)
    return [];

  // Go through this tr and collect divs.
  var comments = hooks[self.hookPos].getElementsByTagName("div");
  if (comments && comments.length == 0) {
    // Don't give up too early and look a bit forward
    var sibling = hooks[self.hookPos].nextSibling;
    while (sibling && sibling.tagName != "TR") {
      sibling = sibling.nextSibling;
    }
    comments = sibling.getElementsByTagName("div");
  }
  return comments;
}


// Intra-line diff handling

/**
 * IntraLineDiff class. Initializes structures to keep track of highlighting
 * state.
 * @constructor
 */
function M_IntraLineDiff() {
  /**
   * Whether we are showing intra-line changes or not
   * @type Boolean
   */
  this.intraLine = true;

  /**
   * "oldreplace" css rule
   * @type CSSStyleRule
   */
  this.oldReplace = null;

  /**
   * "oldlight" css rule
   * @type CSSStyleRule
   */
  this.oldLight = null;

  /**
   * "newreplace" css rule
   * @type CSSStyleRule
   */
  this.newReplace = null;

  /**
   * "newlight" css rule
   * @type CSSStyleRule
   */
  this.newLight = null;

  /**
   * backup of the "oldreplace" css rule's background color
   * @type DOMString
   */
  this.saveOldReplaceBkgClr = null;

  /**
   * backup of the "newreplace" css rule's background color
   * @type DOMString
   */
  this.saveNewReplaceBkgClr = null;

  /**
   * "oldreplace1" css rule's background color
   * @type DOMString
   */
  this.oldIntraBkgClr = null;

  /**
   * "newreplace1" css rule's background color
   * @type DOMString
   */
  this.newIntraBkgClr = null;

  this.findStyles_();
}

/**
 * Finds the styles in the document and keeps references to them in this class
 * instance.
 */
M_IntraLineDiff.prototype.findStyles_ = function() {
  var ss = document.styleSheets[0];
  var rules = [];
  if (ss.cssRules) {
    rules = ss.cssRules;
  } else if (ss.rules) {
    rules = ss.rules;
  }
  for (var i = 0; i < rules.length; i++) {
    var rule = rules[i];
    if (rule.selectorText == ".oldreplace1") {
      this.oldIntraBkgClr = rule.style.backgroundColor;
    } else if (rule.selectorText == ".newreplace1") {
      this.newIntraBkgClr = rule.style.backgroundColor;
    } else if (rule.selectorText == ".oldreplace") {
      this.oldReplace = rule;
      this.saveOldReplaceBkgClr = this.oldReplace.style.backgroundColor;
    } else if (rule.selectorText == ".newreplace") {
      this.newReplace = rule;
      this.saveNewReplaceBkgClr = this.newReplace.style.backgroundColor;
    } else if (rule.selectorText == ".oldlight") {
      this.oldLight = rule;
    } else if (rule.selectorText == ".newlight") {
      this.newLight = rule;
    }
  }
};

/**
 * Toggle the highlighting of the intra line diffs, alternatively turning
 * them on and off.
 */
M_IntraLineDiff.prototype.toggle = function() {
  if (this.intraLine) {
    this.oldReplace.style.backgroundColor = this.oldIntraBkgClr;
    this.oldLight.style.backgroundColor = this.oldIntraBkgClr;
    this.newReplace.style.backgroundColor = this.newIntraBkgClr;
    this.newLight.style.backgroundColor = this.newIntraBkgClr;
    this.intraLine = false;
  } else {
    this.oldReplace.style.backgroundColor = this.saveOldReplaceBkgClr;
    this.oldLight.style.backgroundColor = this.saveOldReplaceBkgClr;
    this.newReplace.style.backgroundColor = this.saveNewReplaceBkgClr;
    this.newLight.style.backgroundColor = this.saveNewReplaceBkgClr;
    this.intraLine = true;
  }
};

/**
 * A click handler common to just about every page, set in global.html.
 * @param {Event} evt The event object that triggered this handler.
 * @return false if the event was handled.
 */
function M_clickCommon(evt) {
  if (helpDisplayed) {
    var help = document.getElementById("help");
    help.style.display = "none";
    helpDisplayed = false;
    return false;
  }
  return true;
}

/**
 * Get a name for key combination of keydown event.
 *
 * See also http://unixpapa.com/js/key.html
 */
function M_getKeyName(evt) {
  var name = "";
  if (evt.ctrlKey)  { name += "Ctrl-" }
  if (evt.altKey)   { name += "Alt-" }
  if (evt.shiftKey) { name += "Shift-" }
  if (evt.metaKey) { name += "Meta-" }
  // Character keys have codes of corresponding ASCII symbols
  if (evt.keyCode >= 65 && evt.keyCode <= 90) {
    return name + String.fromCharCode(evt.keyCode);
  }
  // Numeric keys seems to have codes of corresponding ASCII symbols too
  if (evt.keyCode >= 48 && evt.keyCode <= 57) {
    return name + String.fromCharCode(evt.keyCode);
  }
  // Handling special keys
  switch (evt.keyCode) {
  case 27: return name + "Esc";
  case 13: return name + "Enter";
  case 188: return name + ",";  //  [,<]
  case 190: return name + ".";  //  [.>]
  case 191: return name + "/";  //  [/?]
  case 38: return name + "ArrowUp";
  case 40: return name + "ArrowDown";
  case 17: // Ctrl
  case 18: // Alt
  case 16: // Shift
  // case ??: Meta ?
           return name.substr(0, name.lenght-1);
  default:
    name += "<"+evt.keyCode+">";
  }
  return name;
}

/**
 * Common keydown handler for all pages.
 * @param {Event} evt The event object that triggered this callback
 * @param {function(string)} handler Handles the specific key name;
 *        returns false if the key was handled.
 * @param {function(Event, Node, int, string)} input_handler
 *        Handles the event in case that the event source is an input field.
 *        returns false if the key press was handled.
 * @return false if the event was handled
 */
function M_keyDownCommon(evt, handler, input_handler) {
  if (!evt) var evt = window.event; // for IE
  var target = M_getEventTarget(evt);
  var keyName = M_getKeyName(evt);
  if (target.nodeName == "TEXTAREA" || target.nodeName == "INPUT") {
    if (input_handler) {
      return input_handler(target, keyName);
    }
    return true;
  }
  if (keyName == 'Shift-/' /* '?' */ || keyName == 'Esc') {
    var help = document.getElementById("help");
    if (help) {
      // Only allow the help to be turned on with the ? key.
      if (helpDisplayed || keyName == 'Shift-/') {
        helpDisplayed = !helpDisplayed;
        help.style.display = helpDisplayed ? "" : "none";
        return false;
      }
    }
  }
  return handler(keyName);
}

/**
 * Helper event handler for the keydown event in a comment textarea.
 * @param {Event} evt The event object that triggered this callback
 * @param {Node} src The textarea document element
 * @param {String} key The string with combination name
 * @return false if the event was handled
 */
function M_commentTextKeyDown_(src, key) {
  if (src.nodeName == "TEXTAREA") {
    if (key == 'Ctrl-S' || key == 'Ctrl-Enter') {
      // Save the form corresponding to this text area.
      M_disableCarefulUnload();
      if (src.form.save.onclick) {
        return src.form.save.onclick();
      } else {
        src.form.submit();
        return false;
      }
    }
    if (key == 'Esc') {
      if (src.getAttribute('id') == draftMessage.id_textarea)
      {
        draftMessage.dialog_hide(true);
        src.blur();
        return false;
      } else {
        // textarea of inline comment
        return src.form.cancel.onclick();
      }
    }
  }
  return true;
}

/**
 * Helper to find an item by its elementId and jump to it.  If the item
 * cannot be found this will jump to the changelist instead.
 * @param {elementId} the id of an element an href
 */
function M_jumpToHrefOrChangelist(elementId) {
  var hrefElement = document.getElementById(elementId);
  if (hrefElement) {
    document.location.href = hrefElement.href;
  } else {
    M_upToChangelist();
  }
}

/**
 * Event handler for the keydown event in the file view.
 * @param {Event} evt The event object that triggered this callback
 * @return false if the event was handled
 */
function M_keyDown(evt) {
  return M_keyDownCommon(evt, function(key) {
    if (key == 'N') {
      // next diff
      if (hookState) hookState.gotoNextHook();
    } else if (key == 'P') {
      // previous diff
      if (hookState) hookState.gotoPrevHook();
    } else if (key == 'Shift-N') {
      // next comment
      if (hookState) hookState.gotoNextHook(true);
    } else if (key == 'Shift-P') {
      // previous comment
      if (hookState) hookState.gotoPrevHook(true);
    } else if (key == 'ArrowDown') {
      if (hookState) hookState.gotoLine(1);
    } else if (key == 'ArrowUp') {
      if (hookState) hookState.gotoLine(-1);
    } else if (key == 'J') {
      // next file
      M_jumpToHrefOrChangelist('nextFile')
    } else if (key == 'K') {
      // prev file
      M_jumpToHrefOrChangelist('prevFile')
    } else if (key == 'Shift-J') {
      // next file with comment
      M_jumpToHrefOrChangelist('nextFileWithComment')
    } else if (key == 'Shift-K') {
      // prev file with comment
      M_jumpToHrefOrChangelist('prevFileWithComment')
    } else if (key == 'U') {
      // up to CL
      M_upToChangelist();
    } else if (key == 'I') {
      // toggle intra line diff
      if (intraLineDiff) intraLineDiff.toggle();
    } else if (key == 'S') {
      // toggle show/hide inline comments
      M_toggleAllInlineComments();
    } else if (key == 'E') {
      M_expandAllInlineComments();
    } else if (key == 'C') {
      M_collapseAllInlineComments();
    } else {
      return true;
    }
    return false;
  }, M_commentTextKeyDown_);
}

/**
 * Event handler for the keydown event in the changelist (issue) view.
 * @param {Event} evt The event object that triggered this callback
 * @return false if the event was handled
 */
function M_changelistKeyDown(evt) {
  return M_keyDownCommon(evt, function(key) {
    if (key == 'O' || key == 'Enter') {
      if (dashboardState) {
	var child = dashboardState.curTR.cells[3].firstChild;
	while (child && child.nextSibling && child.nodeName != "A") {
	  child = child.nextSibling;
	}
	if (child && child.nodeName == "A") {
	  location.href = child.href;
	}
      }
    } else if (key == 'I') {
      if (dashboardState) {
	var child = dashboardState.curTR.cells[2].firstChild;
	while (child && child.nextSibling &&
	       (child.nodeName != "A" || child.style.display == "none")) {
	  child = child.nextSibling;
	}
	if (child && child.nodeName == "A") {
	  location.href = child.href;
	}
      }
    } else if (key == 'K') {
      if (dashboardState) dashboardState.gotoPrev();
    } else if (key == 'J') {
      if (dashboardState) dashboardState.gotoNext();
    } else if (key == 'U') {
      // back to dashboard
      document.location.href = base_url;
    } else if (key == 'Esc') {
      M_closePendingTrybots();
    } else {
      return true;
    }
    return false;
  });
}

/**
 * A mouse down handler for the change list page.  Dismissed the try bot
 * popup if visible.
 * @param {Event} evt The event object that triggered this handler.
 * @return false if the event was handled.
 */
function M_changelistMouseDown(evt) {
  var trybotPopup = document.getElementById('trybot-popup');
  if (trybotPopup && trybotPopup.style.display != 'none') {
    var target = M_getEventTarget(evt);
    while(target) {
      if (target == trybotPopup)
        return true;
      target = target.parentNode;
    }
    trybotPopup.style.display = 'none';
    return false;
  }
  return true;
}

/**
 * Goes from the file view back up to the changelist view.
 */
function M_upToChangelist() {
  var upCL = document.getElementById('upCL');
  if (upCL) {
    document.location.href = upCL.href;
  }
}

/**
 * Asynchronously request static analysis warnings as comments.
 * @param {String} cl The current changelist
 * @param {String} depot_path The id of the target element
 * @param {String} a The version number of the left side to be analyzed
 * @param {String} b The version number of the right side to be analyzed
 */
function M_getBugbotComments(cl, depot_path, a, b) {
  var httpreq = M_getXMLHttpRequest();
  if (!httpreq) {
    return;
  }

  // Konqueror jumps to a random location for some reason
  var scrollTop = M_getScrollTop(window);

  httpreq.onreadystatechange = function () {
    // Firefox 2.0, at least, runs this with readyState = 4 but all other
    // fields unset when the timeout aborts the request, against all
    // documentation.
    if (httpreq.readyState == 4) {
      if (httpreq.status == 200) {
        M_updateWarningStatus(httpreq.responseText);
      }
      if (M_isKHTML()) {
        window.scrollTo(0, scrollTop);
      }
    }
  }
  httpreq.open("GET", base_url + "warnings/" + cl + "/" + depot_path +
               "?a=" + a + "&b=" + b, true);
  httpreq.send(null);
}

/**
 * Updates a warning status td with the given HTML.
 * @param {String} result The new html to replace the existing content
 */
function M_updateWarningStatus(result) {
  var elem = document.getElementById("warnings");
  elem.innerHTML = result;
  if (hookState) hookState.updateHooks();
}

/* Ripped off from Caribou */
var M_CONFIRM_DISCARD_NEW_MSG = "Your draft comment has not been saved " +
                                "or sent.\n\nDiscard your comment?";

var M_useCarefulUnload = true;


/**
 * Return an alert if the specified textarea is visible and non-empty.
 */
function M_carefulUnload(text_area_id) {
  return function () {
    var text_area = document.getElementById(text_area_id);
    if (!text_area) return;
    var text_parent = M_getParent(text_area);
    if (M_useCarefulUnload && text_area.style.display != "none"
                           && text_parent.style.display != "none"
                           && goog.string.trim(text_area.value)) {
      return M_CONFIRM_DISCARD_NEW_MSG;
    }
  };
}

function M_disableCarefulUnload() {
  M_useCarefulUnload = false;
}

// History Table

/**
 * Toggles visibility of the snapshots that belong to the given parent.
 * @param {String} parent The parent's index
 * @param {Boolean} opt_show If present, whether to show or hide the group
 */
function M_toggleGroup(parent, opt_show) {
  var children = M_historyChildren[parent];
  if (children.length == 1) {  // No children.
    return;
  }

  var show = (typeof opt_show != "undefined") ? opt_show :
    (document.getElementById("history-" + children[1]).style.display != "");
  for (var i = 1; i < children.length; i++) {
    var child = document.getElementById("history-" + children[i]);
    child.style.display = show ? "" : "none";
  }

  var arrow = document.getElementById("triangle-" + parent);
  if (arrow) {
    arrow.className = "triangle-" + (show ? "open" : "closed");
  }
}

/**
 * Makes the given groups visible.
 * @param {Array.<Number>} parents The indexes of the parents of the groups
 *     to show.
 */
function M_expandGroups(parents) {
  for (var i = 0; i < parents.length; i++) {
    M_toggleGroup(parents[i], true);
  }
  document.getElementById("history-expander").style.display = "none";
  document.getElementById("history-collapser").style.display = "";
}

/**
 * Hides the given parents, except for groups that contain the
 * selected radio buttons.
 * @param {Array.<Number>} parents The indexes of the parents of the groups
 *     to hide.
 */
function M_collapseGroups(parents) {
  // Find the selected snapshots
  var parentsToLeaveOpen = {};
  var form = document.getElementById("history-form");
  var formLength = form.a.length;
  for (var i = 0; i < formLength; i++) {
    if (form.a[i].checked || form.b[i].checked) {
      var element = "history-" + form.a[i].value;
      var name = document.getElementById(element).getAttribute("name");
      if (name != "parent") {
        // The name of a child is "parent-%d" % parent_index.
        var parentIndex = Number(name.match(/parent-(\d+)/)[1]);
        parentsToLeaveOpen[parentIndex] = true;
      }
    }
  }

  // Collapse the parents we need to collapse.
  for (var i = 0; i < parents.length; i++) {
    if (!(parents[i] in parentsToLeaveOpen)) {
      M_toggleGroup(parents[i], false);
    }
  }
  document.getElementById("history-expander").style.display = "";
  document.getElementById("history-collapser").style.display = "none";
}

/**
 * Expands the reverted files section of the files list in the changelist view.
 *
 * @param {String} tableid The id of the table element that contains hidden TR's
 * @param {String} hide The id of the element to hide after this is completed.
 */
function M_showRevertedFiles(tableid, hide) {
  var table = document.getElementById(tableid);
  if (!table) return;
  var rowsLength = table.rows.length;
  for (var i = 0; i < rowsLength; i++) {
    var row = table.rows[i];
    if (row.getAttribute("name") == "afile") row.style.display = "";
  }
  if (dashboardState) dashboardState.initialize();
  var h = document.getElementById(hide);
  if (h) h.style.display = "none";
}


// Dashboard CL navigation

/**
 * M_DashboardState class. Keeps track of the current position of
 * the selector on the dashboard, and moves it on keydown.
 * @param {Window} win The window that the dashboard table is in.
 * @param {String} trName The name of TRs that we will move between.
 * @param {String} cookieName The cookie name to store the marker position into.
 * @constructor
 */
function M_DashboardState(win, trName, cookieName) {
  /**
   * The position of the marker, 0-indexed into the trCache array.
   * @ype Integer
   */
  this.trPos = 0;

  /**
   * The current TR object that the marker is pointing at.
   * @type Element
   */
  this.curTR = null;

  /**
   * Array of tr rows that we are moving between. Computed once (updateable).
   * @type Array
   */
  this.trCache = [];

  /**
   * The window that the table is in, used for positioning information.
   * @type Window
   */
  this.win = win;

  /**
   * The expected name of tr's that we are going to cache.
   * @type String
   */
  this.trName = trName;

  /**
   * The name of the cookie value where the marker position is stored.
   * @type String
   */
  this.cookieName = cookieName;

  this.initialize();
}

/**
 * Initializes the clCache array, and moves the marker into the first position.
 */
M_DashboardState.prototype.initialize = function() {
  var filter = function(arr, lambda) {
    var ret = [];
    var arrLength = arr.length;
    for (var i = 0; i < arrLength; i++) {
      if (lambda(arr[i])) {
	ret.push(arr[i]);
      }
    }
    return ret;
  };
  var cache;
  if (M_isIE()) {
    // IE does not recognize the 'name' attribute on TR tags
    cache = filter(document.getElementsByTagName("TR"),
		   function (elem) { return elem.name == this.trName; });
  } else {
    cache = document.getElementsByName(this.trName);
  }

  this.trCache = filter(cache, function (elem) {
    return elem.style.display != "none";
  });

  if (document.cookie && this.cookieName) {
    cookie_values = document.cookie.split(";");
    for (var i=0; i<cookie_values.length; i++) {
      name = cookie_values[i].split("=")[0].replace(/ /g, '');
      if (name == this.cookieName) {
	pos = cookie_values[i].split("=")[1] || 0;
	/* Make sure that the saved position is valid. */
	if (pos > this.trCache.length-1) {
	  pos = 0;
	}
        this.trPos = pos;
      }
    }
  }

  this.goto_(0);
}

/**
 * Moves the cursor to the curCL position, and potentially scrolls the page to
 * bring the cursor into view.
 * @param {Integer} direction Positive for scrolling down, negative for
 *                            scrolling up, and 0 for no scrolling.
 */
M_DashboardState.prototype.goto_ = function(direction) {
  var oldTR = this.curTR;
  if (oldTR) {
    oldTR.cells[0].firstChild.style.visibility = "hidden";
  }
  this.curTR = this.trCache[this.trPos];
  this.curTR.cells[0].firstChild.style.visibility = "";
  if (this.cookieName) {
    document.cookie = this.cookieName+'='+this.trPos;
  }

  if (!M_isElementVisible(this.win, this.curTR)) {
    M_scrollIntoView(this.win, this.curTR, direction);
  }
}

/**
 * Moves the cursor up one.
 */
M_DashboardState.prototype.gotoPrev = function() {
  if (this.trPos > 0) this.trPos--;
  this.goto_(-1);
}

/**
 * Moves the cursor down one.
 */
M_DashboardState.prototype.gotoNext = function() {
  if (this.trPos < this.trCache.length - 1) this.trPos++;
  this.goto_(1);
}

/**
 * Event handler for dashboard hot keys. Dispatches cursor moves, as well as
 * opening CLs.
 */
function M_dashboardKeyDown(evt) {
  return M_keyDownCommon(evt, function(key) {
    if (key == 'K') {
      if (dashboardState) dashboardState.gotoPrev();
    } else if (key == 'J') {
      if (dashboardState) dashboardState.gotoNext();
    } else if (key == 'Shift-3' /* '#' */) {
      if (dashboardState) {
	var child = dashboardState.curTR.cells[1].firstChild;
	while (child && child.className != "issue-close") {
	  child = child.nextSibling;
	}
	if (child) {
	  child = child.firstChild;
	}
	while (child && child.nodeName != "A") {
	  child = child.nextSibling;
	}
	if (child) {
	  location.href = child.href;
	}
      }
    } else if (key == 'O' || key == 'Enter') {
      if (dashboardState) {
	var child = dashboardState.curTR.cells[2].firstChild;
	while (child && child.nodeName != "A") {
	  child = child.firstElementChild;
	}
	if (child) {
	  location.href = child.href;
	}
      }
    } else {
      return true;
    }
    return false;
  });
}

/**
 * Helper to fill a table cell element.
 * @param {Array} attrs An array of attributes to be applied
 * @param {String} text The content of the table cell
 * @return {Element}
 */
function M_fillTableCell_(attrs, text) {
  var td = document.createElement("td");
  for (var j=0; j<attrs.length; j++) {
    if (attrs[j][0] == "class" && M_isIE()) {
      td.setAttribute("className", attrs[j][1]);
    } else {
      td.setAttribute(attrs[j][0], attrs[j][1]);
    }
  }
  if (!text) text = "";
  if (M_isIE()) {
    td.innerText = text;
  } else {
    td.textContent = text;
  }
  return td;
}

/*
 * Function to request more context between diff chunks.
 * See _ShortenBuffer() in codereview/engine.py.
 */
function M_expandSkipped(id_before, id_after, where, id_skip) {
  var links = document.getElementById('skiplinks-'+id_skip).getElementsByTagName('a');
  for (var i=0; i<links.length; i++) {
	links[i].href = '#skiplinks-'+id_skip;
  }
  var tr = document.getElementById('skip-'+id_skip);
  var httpreq = M_getXMLHttpRequest();
  if (!httpreq) {
    html = '<td colspan="2" style="text-align: center;">';
    html = html + 'Failed to retrieve additional lines. ';
    html = html + 'Please update your context settings.';
    html = html + '</td>';
    tr.innerHTML = html;
  }
  document.getElementById('skiploading-'+id_skip).style.visibility = 'visible';
  var context_select = document.getElementById('id_context');
  var context = null;
  if (context_select) {
    context = context_select.value;
  }
  var aborted = false;
  httpreq.onreadystatechange = function () {
    if (httpreq.readyState == 4 && !aborted) {
      if (httpreq.status == 200) {
        var response = eval('('+httpreq.responseText+')');
	var last_row = null;
        for (var i=0; i<response.length; i++) {
          var data = response[i];
          var row = document.createElement("tr");
          for (var j=0; j<data[0].length; j++) {
            if (data[0][j][0] == "class" && M_isIE()) {
              row.setAttribute("className", data[0][j][1]);
            } else {
              row.setAttribute(data[0][j][0], data[0][j][1]);
            }
          }
          if ( where == 't' || where == 'a') {
            tr.parentNode.insertBefore(row, tr);
          } else {
	    if (last_row) {
              tr.parentNode.insertBefore(row, last_row.nextSibling);
	    } else {
	      tr.parentNode.insertBefore(row, tr.nextSibling);
	    }
          }
          var left = M_fillTableCell_(data[1][0][0], data[1][0][1]);
          var right = M_fillTableCell_(data[1][1][0], data[1][1][1]);
          row.appendChild(left);
          row.appendChild(right);
	  last_row = row;
        }
        var curr = document.getElementById('skipcount-'+id_skip);
        var new_count = parseInt(curr.innerHTML)-response.length/2;
        if ( new_count > 0 ) {
          if ( where == 'b' ) {
            var new_before = id_before;
            var new_after = id_after-response.length/2;
          } else {
            var new_before = id_before+response.length/2;
            var new_after = id_after;
          }
          curr.innerHTML = new_count;
	  html = '';
	  if ( new_count > 3*context ) {
	    html += '<a href="javascript:M_expandSkipped('+new_before;
            html += ','+new_after+',\'t\', '+id_skip+');">';
	    html += 'Expand '+context+' before';
	    html += '</a> | ';
	  }
	  html += '<a href="javascript:M_expandSkipped('+new_before;
	  html += ','+new_after+',\'a\','+id_skip+');">Expand all</a>';
          if ( new_count > 3*context ) {
	    var val = parseInt(new_after);
            html += ' | <a href="javascript:M_expandSkipped('+new_before;
            html += ','+val+',\'b\','+id_skip+');">';
	    html += 'Expand '+context+' after';
	    html += '</a>';
          }
          document.getElementById('skiplinks-'+(id_skip)).innerHTML = html;
	  var loading_node = document.getElementById('skiploading-'+id_skip);
	  loading_node.style.visibility = 'hidden';
        } else {
          tr.parentNode.removeChild(tr);
        }
	hookState.updateHooks();
        if (hookState.hookPos != -2 &&
	    M_isElementVisible(window, hookState.indicator)) {
	  // Restore indicator position on screen, but only if the indicator
	  // is visible. We don't know if we have to scroll up or down to
	  // make the indicator visible. Therefore the current hook is
	  // internally set to the previous hook and
	  // then gotoNextHook() does everything needed to end up with a
	  // clean hookState and the indicator visible on screen.
          hookState.hookPos = hookState.hookPos - 1;
	  hookState.gotoNextHook();
        }
      } else {
	msg = '<td colspan="2" align="center"><span style="color:red;">';
	msg += 'An error occurred ['+httpreq.status+']. ';
	msg += 'Please report.';
	msg += '</span></td>';
	tr.innerHTML = msg;
      }
    }
  }

  colwidth = document.getElementById('id_column_width').value;
  tabspaces = document.getElementById('id_tab_spaces').value;

  url = skipped_lines_url+id_before+'/'+id_after+'/'+where+'/'+colwidth+'/'+tabspaces;
  if (context) {
    url += '?context='+context;
  }
  httpreq.open('GET', url, true);
  httpreq.send('');
}

/**
 * Finds the element position.
 */
function M_getElementPosition(obj) {
  var curleft = curtop = 0;
  if (obj.offsetParent) {
    do {
      curleft += obj.offsetLeft;
      curtop += obj.offsetTop;
    } while (obj = obj.offsetParent);
  }
  return [curleft,curtop];
}

/**
 * Position the user info popup according to the mouse event coordinates
 */
function M_positionUserInfoPopup(obj, userPopupDiv) {
  pos = M_getElementPosition(obj);
  userPopupDiv.style.left = pos[0] + "px";
  userPopupDiv.style.top = pos[1] + 20 + "px";
}

/**
 * Brings up user info popup using ajax
 */
function M_showUserInfoPopup(obj) {
  var DIV_ID = "userPopupDiv";
  var userPopupDiv = document.getElementById(DIV_ID);
  var url = obj.getAttribute("href")
  var index = url.indexOf("/user/");
  var user_key = url.substring(index + 6);

  if (!userPopupDiv) {
    var userPopupDiv = document.createElement("div");
    userPopupDiv.className = "popup";
    userPopupDiv.id = DIV_ID;
    userPopupDiv.filter = 'alpha(opacity=85)';
    userPopupDiv.opacity = '0.85';
    userPopupDiv.innerHTML = "";
    userPopupDiv.onmouseout = function() {
      userPopupDiv.style.visibility = 'hidden';
    }
    document.body.appendChild(userPopupDiv);
  }
  M_positionUserInfoPopup(obj, userPopupDiv);

  var httpreq = M_getXMLHttpRequest();
  if (!httpreq) {
    return true;
  }

  var aborted = false;
  var httpreq_timeout = setTimeout(function() {
    aborted = true;
    httpreq.abort();
  }, 5000);

  httpreq.onreadystatechange = function () {
    if (httpreq.readyState == 4 && !aborted) {
      clearTimeout(httpreq_timeout);
      if (httpreq.status == 200) {
        userPopupDiv = document.getElementById(DIV_ID);
        userPopupDiv.innerHTML=httpreq.responseText;
        userPopupDiv.style.visibility = "visible";
      } else {
        //Better fail silently here because it's not
        //critical functionality
      }
    }
  }
  httpreq.open("GET", base_url + "user_popup/" + user_key, true);
  httpreq.send(null);
  obj.onmouseout = function() {
    aborted = true;
    userPopupDiv.style.visibility = 'hidden';
    obj.onmouseout = null;
  }
}

/**
 * TODO(jiayao,andi): docstring
 */
function M_showPopUp(obj, id) {
  var popup = document.getElementById(id);
  var pos = M_getElementPosition(obj);
  popup.style.left = pos[0]+'px';
  popup.style.top = pos[1]+20+'px';
  popup.style.visibility = 'visible';
  obj.onmouseout = function() {
    popup.style.visibility = 'hidden';
    obj.onmouseout = null;
  }
}

/**
 * Jump to a patch in the changelist.
 * @param {Element} select The select form element.
 * @param {Integer} issue The issue id.
 * @param {Integer} patchset The patchset id.
 * @param {Boolean} unified If True show unified diff else s-b-s view.
 * @param {String} opt_part The type of diff to jump to -- diff/diff2/patch
 */
function M_jumpToPatch(select, issue, patchset, unified, opt_part) {
  var part = opt_part;
  if (!part) {
    if (unified) {
      part = 'patch';
    } else {
      part = 'diff';
    }
  }
  var url = base_url+issue+'/'+part+'/'+patchset+'/'+select.value;
  var context = document.getElementById('id_context');
  var colwidth = document.getElementById('id_column_width');
  var tabspaces = document.getElementById('id_tab_spaces');
  if (context && colwidth && tabspaces) {
    url = url+'?context='+context.value+'&column_width='+colwidth.value+'&tab_spaces='+tabspaces.value;
  }
  document.location.href = url;
}

/**
 * Generic callback when page is unloaded.
 */
function M_unloadPage() {
  if (draftMessage) { draftMessage.save(); }
}
