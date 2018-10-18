/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

var listen;
var unlisten;
var unlistenByKey;

(function() {
  let listeners = {};
  let nextId = 0;

  function getHashCode_(obj) {
    if (obj.listen_hc_ == null) {
      obj.listen_hc_ = ++nextId;
    }
    return obj.listen_hc_;
  }

  /**
   * Takes a node, event, listener, and capture flag to create a key
   * to identify the tuple in the listeners hash.
   *
   * @param {Element} node The node to listen to events on.
   * @param {string} event The name of the event without the "on" prefix.
   * @param {Function} listener A function to call when the event occurs.
   * @param {boolean} opt_useCapture In DOM-compliant browsers, this determines
   *                                 whether the listener is fired during the
   *                                 capture or bubble phase of the event.
   * @return {string} key to identify this tuple in the listeners hash.
   */
  function createKey_(node, event, listener, opt_useCapture) {
    let nodeHc = getHashCode_(node);
    let listenerHc = getHashCode_(listener);
    opt_useCapture = !!opt_useCapture;
    let key = nodeHc + '_' + event + '_' + listenerHc + '_' + opt_useCapture;
    return key;
  }

  /**
   * Adds an event listener to a DOM node for a specific event.
   *
   * Listen() and unlisten() use an indirect lookup of listener functions
   * to avoid circular references between DOM (in IE) or XPCOM (in Mozilla)
   * objects which leak memory. This makes it easier to write OO
   * Javascript/DOM code.
   *
   * Examples:
   * listen(myButton, 'click', myHandler, true);
   * listen(myButton, 'click', this.myHandler.bind(this), true);
   *
   * @param {Element} node The node to listen to events on.
   * @param {string} event The name of the event without the "on" prefix.
   * @param {Function} listener A function to call when the event occurs.
   * @param {boolean} opt_useCapture In DOM-compliant browsers, this determines
   *                                 whether the listener is fired during the
   *                                 capture or bubble phase of the event.
   * @return {string} a unique key to indentify this listener.
   */
  listen = function(node, event, listener, opt_useCapture) {
    let key = createKey_(node, event, listener, opt_useCapture);

    // addEventListener does not allow multiple listeners
    if (key in listeners) {
      return key;
    }

    let proxy = handleEvent.bind(null, key);
    listeners[key] = {
      listener: listener,
      proxy: proxy,
      event: event,
      node: node,
      useCapture: opt_useCapture,
    };

    if (node.addEventListener) {
      node.addEventListener(event, proxy, opt_useCapture);
    } else if (node.attachEvent) {
      node.attachEvent('on' + event, proxy);
    } else {
      throw new Error('Node {' + node + '} does not support event listeners.');
    }

    return key;
  };

  /**
   * Removes an event listener which was added with listen().
   *
   * @param {Element} node The node to stop listening to events on.
   * @param {string} event The name of the event without the "on" prefix.
   * @param {Function} listener The listener function to remove.
   * @param {boolean} opt_useCapture In DOM-compliant browsers, this determines
   *                                 whether the listener is fired during the
   *                                 capture or bubble phase of the event.
   * @return {boolean} indicating whether the listener was there to remove.
   */
  unlisten = function(node, event, listener, opt_useCapture) {
    let key = createKey_(node, event, listener, opt_useCapture);

    return unlistenByKey(key);
  };

  /**
   * Variant of {@link unlisten} that takes a key that was returned by
   * {@link listen} and removes that listener.
   *
   * @param {string} key Key of event to be unlistened.
   * @return {boolean} indicating whether it was there to be removed.
   */
  unlistenByKey = function(key) {
    if (!(key in listeners)) {
      return false;
    }
    let listener = listeners[key];
    let proxy = listener.proxy;
    let event = listener.event;
    let node = listener.node;
    let useCapture = listener.useCapture;

    if (node.removeEventListener) {
      node.removeEventListener(event, proxy, useCapture);
    } else if (node.detachEvent) {
      node.detachEvent('on' + event, proxy);
    }

    delete listeners[key];
    return true;
  };

  /**
   * The function which is actually called when the DOM event occurs. This
   * function is a proxy for the real listener the user specified.
   */
  function handleEvent(key) {
    // pass all arguments which were sent to this function except listenerID
    // on to the actual listener.
    let args = Array.prototype.splice.call(arguments, 1, arguments.length);
    return listeners[key].listener.apply(null, args);
  }
})();
