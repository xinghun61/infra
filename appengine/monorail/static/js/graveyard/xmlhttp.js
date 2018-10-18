/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * @fileoverview A bunch of XML HTTP recipes used to do RPC from JavaScript
 */


/**
 * The active x identifier used for ie.
 * @type String
 * @private
 */
var XH_ieProgId_;


// Domain for XMLHttpRequest readyState
var XML_READY_STATE_UNINITIALIZED = 0;
var XML_READY_STATE_LOADING = 1;
var XML_READY_STATE_LOADED = 2;
var XML_READY_STATE_INTERACTIVE = 3;
var XML_READY_STATE_COMPLETED = 4;


/**
 * Initialize the private state used by other functions.
 * @private
 */
function XH_XmlHttpInit_() {
  // The following blog post describes what PROG IDs to use to create the
  // XMLHTTP object in Internet Explorer:
  // http://blogs.msdn.com/xmlteam/archive/2006/10/23/using-the-right-version-of-msxml-in-internet-explorer.aspx
  // However we do not (yet) fully trust that this will be OK for old versions
  // of IE on Win9x so we therefore keep the last 2.
  // Versions 4 and 5 have been removed because 3.0 is the preferred "fallback"
  // per the article above.
  // - Version 5 was built for Office applications and is not recommended for
  //   web applications.
  // - Version 4 has been superseded by 6 and is only intended for legacy apps.
  // - Version 3 has a wide install base and is serviced regularly with the OS.

  /**
   * Candidate Active X types.
   * @type Array.<String>
   * @private
   */
  let XH_ACTIVE_X_IDENTS = ['MSXML2.XMLHTTP.6.0', 'MSXML2.XMLHTTP.3.0',
    'MSXML2.XMLHTTP', 'Microsoft.XMLHTTP'];

  if (typeof XMLHttpRequest == 'undefined' &&
      typeof ActiveXObject != 'undefined') {
    for (let i = 0; i < XH_ACTIVE_X_IDENTS.length; i++) {
      let candidate = XH_ACTIVE_X_IDENTS[i];

      try {
        new ActiveXObject(candidate);
        XH_ieProgId_ = candidate;
        break;
      } catch (e) {
        // do nothing; try next choice
      }
    }

    // couldn't find any matches
    if (!XH_ieProgId_) {
      throw Error('Could not create ActiveXObject. ActiveX might be disabled,' +
                  ' or MSXML might not be installed.');
    }
  }
}


XH_XmlHttpInit_();


/**
 * Create and return an xml http request object that can be passed to
 * {@link #XH_XmlHttpGET} or {@link #XH_XmlHttpPOST}.
 */
function XH_XmlHttpCreate() {
  if (XH_ieProgId_) {
    return new ActiveXObject(XH_ieProgId_);
  } else {
    return new XMLHttpRequest();
  }
}


/**
 * Send a get request.
 * @param {XMLHttpRequest} xmlHttp as from {@link XH_XmlHttpCreate}.
 * @param {string} url the service to contact
 * @param {Function} handler function called when the response is received.
 */
function XH_XmlHttpGET(xmlHttp, url, handler) {
  xmlHttp.open('GET', url, true);
  xmlHttp.onreadystatechange = handler;
  XH_XmlHttpSend(xmlHttp, null);
}

/**
 * Send a post request.
 * @param {XMLHttpRequest} xmlHttp as from {@link XH_XmlHttpCreate}.
 * @param {string} url the service to contact
 * @param {string} data the request content.
 * @param {Function} handler function called when the response is received.
 */
function XH_XmlHttpPOST(xmlHttp, url, data, handler) {
  xmlHttp.open('POST', url, true);
  xmlHttp.onreadystatechange = handler;
  xmlHttp.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  XH_XmlHttpSend(xmlHttp, data);
}

/**
 * Calls 'send' on the XMLHttpRequest object and calls a function called 'log'
 * if any error occured.
 *
 * @deprecated This dependes on a function called 'log'. You are better off
 * handling your errors on application level.
 *
 * @param {XMLHttpRequest} xmlHttp as from {@link XH_XmlHttpCreate}.
 * @param {string|null} data the request content.
 */
function XH_XmlHttpSend(xmlHttp, data) {
  try {
    xmlHttp.send(data);
  } catch (e) {
    // You may want to log/debug this error one that you should be aware of is
    // e.number == -2146697208, which occurs when the 'Languages...' setting in
    // IE is empty.
    // This is not entirely true. The same error code is used when the user is
    // off line.
    console.log('XMLHttpSend failed ' + e.toString() + '<br>' + e.stack);
    throw e;
  }
}
