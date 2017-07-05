/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * @fileoverview This file represents a standalone, reusable drop down menu
 * widget that can be attached to any element on a given page. It supports
 * multiple instances of the widget on a page. It has no dependencies. Usage
 * is as simple as creating a new Menu object and supplying it with a target
 * element.
 */

/**
 * The entry point and constructor for the Menu object. Creating
 * a valid instance of this object will insert a drop down menu
 * near the element supplied as the target, attach all the necessary
 * events and insert the necessary elements on the page.
 *
 * @param {Element} target the target element on the page to which
 *     the drop down menu will be placed near.
 * @param {Function=} opt_onShow function to execute every time the
 *     menu is made visible, most likely through a click on the target.
 * @constructor
 */
var Menu = function(target, opt_onShow) {
  this.iid = Menu.instance.length;
  Menu.instance[this.iid] = this;
  this.target = target;
  this.onShow = opt_onShow || null;

  // An optional trigger element on the page that can be used to trigger
  // the drop-down. Currently hard-coded to be the same as the target element.
  this.trigger = target;
  this.items = [];
  this.onOpenEvents = [];
  this.menu = this.createElement('div', 'menuDiv instance' + this.iid);
  this.targetId = this.target.getAttribute('id');
  var menuId = (this.targetId != null) ?
      'menuDiv-' + this.targetId : 'menuDiv-instance' + this.iid;
  this.menu.setAttribute('id', menuId);
  this.menu.role = 'listbox';
  this.hide();
  this.addCategory('default');
  this.addEvent(this.trigger, 'click', this.toggle.bind(this));
  this.addEvent(window, 'resize', this.adjustSizeAndLocation.bind(this));

  // Hide the menu if a user clicks outside the menu widget
  this.addEvent(document, 'click', this.hide.bind(this));
  this.addEvent(this.menu, 'click', this.stopPropagation());
  this.addEvent(this.trigger, 'click', this.stopPropagation());
};

// A reference to the element or node that the drop down
// will appear next to
Menu.prototype.target = null;

// Element ID of the target. ID will be assigned to the newly created
// menu div based on the target ID. A default ID will be
// assigned If there is no ID on the target.
Menu.prototype.targetId = null;

/**
 * A reference to the element or node that will trigger
 * the drop down to appear. If not specified, this value
 * will be the same as <Menu Instance>.target
 * @type {Element}
 */
Menu.prototype.trigger = null;

// A reference to the event type that will "open" the
// menu div. By default this is the (on)click method.
Menu.prototype.triggerType = null;

// A reference to the element that will appear when the
// trigger is clicked.
Menu.prototype.menu = null;

/**
 * Function to execute every time the menu is made shown.
 * @type {Function}
 */
Menu.prototype.onShow = null;

// A list of category divs. By default these categories
// are set to display none until at least one element
// is placed within them.
Menu.prototype.categories = null;

// An id used to track timed intervals
Menu.prototype.thread = -1;

// The static instance id (iid) denoting which menu in the
// list of Menu.instance items is this instantiated object.
Menu.prototype.iid = -1;

// A counter to indicate the number of items added with
// addItem(). After 5 items, a height is set on the menu
// and a scroll bar will appear.
Menu.prototype.items = null;

// A flag to detect whether or not a scroll bar has been added
Menu.prototype.scrolls = false;

// onOpen event handlers; each function in this list will
// be executed and passed the executing instance as a
// parameter before the menu is to be displayed.
Menu.prototype.onOpenEvents = null;

/**
 * An extended short-cut for document.createElement(); this
 * method allows the creation of an element, the assignment
 * of one or more class names and the ability to set the
 * content of the created element all with one function call.
 * @param {string} element name of the element to create. Examples would
 *     be 'div' or 'a'.
 * @param {string} opt_className an optional string to assign to the
 *     newly created element's className property.
 * @param {string|Element} opt_content either a snippet of HTML or a HTML
 *     element that is to be appended to the newly created element.
 * @return {Element} a reference to the newly created element.
 */
Menu.prototype.createElement = function(element, opt_className, opt_content) {
  var div = document.createElement(element);
  div.className = opt_className;
  if (opt_content) {
    this.append(opt_content, div);
  }
  return div;
};

/**
 * Uses a fairly browser agnostic approach to applying a callback to
 * an element on the page.
 *
 * @param {Element|EventTarget} element a reference to an element on the page to
 *     which to attach and event.
 * @param {string} eventType a browser compatible event type as a string
 *     without the sometimes assumed on- prefix. Examples: 'click',
 *     'mousedown', 'mouseover', etc...
 * @param {Function} callback a function reference to invoke when the
 *     the event occurs.
 */
Menu.prototype.addEvent = function(element, eventType, callback) {
  if (element.addEventListener) {
    element.addEventListener(eventType, callback, false);
  } else {
    try {
      element.attachEvent('on' + eventType, callback);
    } catch (e) {
      element['on' + eventType] = callback;
    }
  }
};

/**
 * Similar to addEvent, this provides a specialied handler for onOpen
 * events that apply to this instance of the Menu class. The supplied
 * callbacks are appended to an internal array and called in order
 * every time the menu is opened. The array can be accessed via
 * menuInstance.onOpenEvents.
 */
Menu.prototype.addOnOpen = function(eventCallback) {
  var eventIndex = this.onOpenEvents.length;
  this.onOpenEvents.push(eventCallback);
  return eventIndex;
};

/**
 * This method will create a div with the classes .menuCategory and the
 * name of the category as supplied in the first parameter. It then, if
 * a title is supplied, creates a title div and appends it as well. The
 * optional title is styled with the .categoryTitle and category name
 * class.
 *
 * Categories are stored within the menu object instance for programmatic
 * manipulation in the array, menuInstance.categories. Note also that this
 * array is doubly linked insofar as that the category div can be accessed
 * via it's index in the array as well as by instance.categories[category]
 * where category is the string name supplied when creating the category.
 *
 * @param {string} category the string name used to create the category;
 *     used as both a class name and a key into the internal array. It
 *     must be a valid JavaScript variable name.
 * @param {string|Element} opt_title this optional field is used to visibly
 *     denote the category title. It can be either HTML or an element.
 * @return {Element} the newly created div.
 */
Menu.prototype.addCategory = function(category, opt_title) {
  this.categories = this.categories || [];
  var categoryDiv = this.createElement('div', 'menuCategory ' + category);
  categoryDiv._categoryName = category;
  if (opt_title) {
    var categoryTitle = this.createElement('b', 'categoryTitle ' +
          category, opt_title);
    categoryTitle.style.display = 'block';
    this.append(categoryTitle);
    categoryDiv._categoryTitle = categoryTitle;
  }
  this.append(categoryDiv);
  this.categories[this.categories.length] = this.categories[category] =
      categoryDiv;

  return categoryDiv;
};

/**
 * This method removes the contents of a given category but does not
 * remove the category itself.
 */
Menu.prototype.emptyCategory = function(category) {
  if (!this.categories[category]) {
    return;
  }
  var div = this.categories[category];
  for (var i = div.childNodes.length - 1; i >= 0; i--) {
    div.removeChild(div.childNodes[i]);
  }
};

/**
 * This function is the most drastic of the cleansing functions; it removes
 * all categories and all menu items and all HTML snippets that have been
 * added to this instance of the Menu class.
 */
Menu.prototype.clear = function() {
  for (var i = 0; i < this.categories.length; i++) {
    // Prevent memory leaks
    this.categories[this.categories[i]._categoryName] = null;
  }
  this.items.splice(0, this.items.length);
  this.categories.splice(0, this.categories.length);
  this.categories = [];
  this.items = [];
  for (var i = this.menu.childNodes.length - 1; i >= 0; i--) {
    this.menu.removeChild(this.menu.childNodes[i]);
  }
};

/**
 * Passed an instance of a menu item, it will be removed from the menu
 * object, including any residual array links and possible memory leaks.
 * @param {Element} item a reference to the menu item to remove.
 * @return {Element} returns the item removed.
 */
Menu.prototype.removeItem = function(item) {
  var result = null;
  for (var i = 0; i < this.items.length; i++) {
    if (this.items[i] == item) {
      result = this.items[i];
      this.items.splice(i, 1);
    }
    // Renumber
    this.items[i].item._index = i;
  }
  return result;
};

/**
 * Removes a category from the menu element and all of its children thus
 * allowing the Element to be collected by the browsers VM.
 * @param {string} category the name of the category to retrieve and remove.
 */
Menu.prototype.removeCategory = function(category) {
  var div = this.categories[category];
  if (!div || !div.parentNode) {
    return;
  }
  if (div._categoryTitle) {
    div._categoryTitle.parentNode.removeChild(div._categoryTitle);
  }
  div.parentNode.removeChild(div);
  for (var i = 0; i < this.categories.length; i++) {
    if (this.categories[i] === div) {
      this.categories[this.categories[i]._categoryName] = null;
      this.categories.splice(i, 1);
      return;
    }
  }
  for (var i = 0; i < div.childNodes.length; i++) {
    if (div.childNodes[i]._index) {
      this.items.splice(div.childNodes[i]._index, 1);
    } else {
      this.removeItem(div.childNodes[i]);
    }
  }
};

/**
 * This heart of the menu population scheme, the addItem function creates
 * a combination of elements that visually form up a menu item. If no
 * category is supplied, the default category is used. The menu item is
 * an <a> tag with the class .menuItem. The menu item is directly styled
 * as a block element. Other than that, all styling should be done via a
 * external CSS definition.
 *
 * @param {string|Element} html_or_element a string of HTML text or a
 *     HTML element denoting the contents of the menu item.
 * @param {string} opt_href the href of the menu item link. This is
 *     the most direct way of defining the menu items function.
 *     [Default: '#'].
 * @param {string} opt_category the category string name of the category
 *     to append the menu item to. If the category doesn't exist, one will
 *     be created. [Default: 'default'].
 * @param {string} opt_title used when creating a new category and is
 *     otherwise ignored completely. It is also ignored when supplied if
 *     the named category already exists.
 * @return {Element} returns the element that was created.
 */
Menu.prototype.addItem = function(html_or_element, opt_href, opt_category,
                                  opt_title) {
  var category = opt_category ? (this.categories[opt_category] ||
                                 this.addCategory(opt_category, opt_title)) :
      this.categories['default'];
  var menuHref = (opt_href == undefined ? '#' : opt_href);
  var menuItem = undefined;
  if (menuHref) {
    menuItem = this.createElement('a', 'menuItem', html_or_element);
  } else {
    menuItem = this.createElement('span', 'menuText', html_or_element);
  }
  var itemText = typeof html_or_element == 'string' ? html_or_element :
      html_or_element.textContent || 'ERROR';

  menuItem.style.display = 'block';
  if (menuHref) {
    menuItem.setAttribute('href', menuHref);
  }
  menuItem._index = this.items.length;
  menuItem.role = 'option';
  this.append(menuItem, category);
  this.items[this.items.length] = {item: menuItem, text: itemText};

  return menuItem;
};

/**
 * Adds a visual HTML separator to the menu, optionally creating a
 * category as per addItem(). See above.
 * @param {string} opt_category the category string name of the category
 *     to append the menu item to. If the category doesn't exist, one will
 *     be created. [Default: 'default'].
 * @param {string} opt_title used when creating a new category and is
 *     otherwise ignored completely. It is also ignored when supplied if
 *     the named category already exists.
 */
Menu.prototype.addSeparator = function(opt_category, opt_title) {
  var category = opt_category ? (this.categories[opt_category] ||
                                 this.addCategory(opt_category, opt_title)) :
      this.categories['default'];
  var hr = this.createElement('hr', 'menuSeparator');
  this.append(hr, category);
};

/**
 * This method performs all the dirty work of positioning the menu. It is
 * responsible for dynamic sizing, insertion and deletion of scroll bars
 * and calculation of offscreen width considerations.
 */
Menu.prototype.adjustSizeAndLocation = function() {
  var style = this.menu.style;
  style.position = 'absolute';

  var firstCategory = null;
  for (var i = 0; i < this.categories.length; i++) {
    this.categories[i].className = this.categories[i].className.
        replace(/ first/, '');
    if (this.categories[i].childNodes.length == 0) {
      this.categories[i].style.display = 'none';
    } else {
      this.categories[i].style.display = '';
      if (!firstCategory) {
        firstCategory = this.categories[i];
        firstCategory.className += ' first';
      }
    }
  }

  var alreadyVisible = style.display != 'none' &&
      style.visibility != 'hidden';
  var docElemWidth = document.documentElement.clientWidth;
  var docElemHeight = document.documentElement.clientHeight;
  var pageSize = {
    w: (window.innerWidth || docElemWidth && docElemWidth > 0 ?
        docElemWidth : document.body.clientWidth) || 1,
    h: (window.innerHeight || docElemHeight && docElemHeight > 0 ?
        docElemHeight : document.body.clientHeight) || 1
  };
  var targetPos = this.find(this.target);
  var targetSize = {w: this.target.offsetWidth,
                    h: this.target.offsetHeight};
  var menuSize = {w: this.menu.offsetWidth, h: this.menu.offsetHeight};

  if (!alreadyVisible) {
    var oldVisibility = style.visibility;
    var oldDisplay = style.display;
    style.visibility = 'hidden';
    style.display = '';
    style.height = '';
    style.width = '';
    menuSize = {w: this.menu.offsetWidth, h: this.menu.offsetHeight};
    style.display = oldDisplay;
    style.visibility = oldVisibility;
  }

  var addScroll = (this.menu.offsetHeight / pageSize.h) > 0.8;
  if (addScroll) {
    menuSize.h = parseInt((pageSize.h * 0.8), 10);
    style.height = menuSize.h + 'px';
    style.overflowX = 'hidden';
    style.overflowY = 'auto';
  } else {
    style.height = style.overflowY = style.overflowX = '';
  }

  style.top = (targetPos.y + targetSize.h) + 'px';
  style.left = targetPos.x + 'px';

  if (menuSize.w < 175) {
    style.width = '175px';
  }

  if (addScroll) {
    style.width = parseInt(style.width, 10) + 13 + 'px';
  }

  if ((targetPos.x + menuSize.w) > pageSize.w) {
    style.left = targetPos.x - (menuSize.w - targetSize.w) + 'px';
  }
};


/**
 * This function is used heavily, internally. It appends text
 * or the supplied element via appendChild(). If
 * the opt_target variable is present, the supplied element will be
 * the container rather than the menu div for this instance.
 *
 * @param {string|Element} text_or_element the html or element to insert
 *     into opt_target.
 * @param {Element} opt_target the target element it should be appended to.
 *
 */
Menu.prototype.append = function(text_or_element, opt_target) {
  var element = opt_target || this.menu;
  if (typeof opt_target == 'string' && this.categories[opt_target]) {
    element = this.categories[opt_target];
  }
  if (typeof text_or_element == 'string') {
    element.textContent += text_or_element;
  } else {
    element.appendChild(text_or_element);
  }
};

/**
 * Displays the menu (such as upon mouseover).
 */
Menu.prototype.over = function() {
  if (this.menu.style.display != 'none') {
    this.show();
  }
  if (this.thread != -1) {
    clearTimeout(this.thread);
    this.thread = -1;
  }
};

/**
 * Hides the menu (such as upon mouseout).
 */
Menu.prototype.out = function() {
  if (this.thread != -1) {
    clearTimeout(this.thread);
    this.thread = -1;
  }
  this.thread = setTimeout(this.hide.bind(this), 400);
};

/**
 * Stops event propagation.
 */
Menu.prototype.stopPropagation = function() {
  return (function(e) {
    if (!e) {
      e = window.event;
    }
    e.cancelBubble = true;
    if (e.stopPropagation) {
      e.stopPropagation();
    }
  });
};

/**
 * Toggles the menu between hide/show.
 */
Menu.prototype.toggle = function(event) {
  event.preventDefault();
  if (this.menu.style.display == 'none') {
    this.show();
  } else {
    this.hide();
  }
};

/**
 * Makes the menu visible, then calls the user-supplied onShow callback.
 */
Menu.prototype.show = function() {
  if (this.menu.style.display != '') {
    for (var i = 0; i < this.onOpenEvents.length; i++) {
      this.onOpenEvents[i].call(null, this);
    }

    // Invisibly show it first
    this.menu.style.visibility = 'hidden';
    this.menu.style.display = '';
    this.adjustSizeAndLocation();
    if (this.trigger.nodeName && this.trigger.nodeName == 'A') {
      this.trigger.blur();
    }
    this.menu.style.visibility = 'visible';

    // Hide other menus
    for (var i = 0; i < Menu.instance.length; i++) {
      var menuInstance = Menu.instance[i];
      if (menuInstance != this) {
        menuInstance.hide();
      }
    }

    if (this.onShow) {
      this.onShow();
    }
  }
};

/**
 * Makes the menu invisible.
 */
Menu.prototype.hide = function() {
  this.menu.style.display = 'none';
};

Menu.prototype.find = function(element) {
  var curleft = 0, curtop = 0;
  if (element.offsetParent) {
    do {
      curleft += element.offsetLeft;
      curtop += element.offsetTop;
    }
    while ((element = element.offsetParent) && (element.style &&
          element.style.position != 'relative' &&
          element.style.position != 'absolute'));
    }
  return {x: curleft, y: curtop};
};

/**
 * A static array of object instances for global reference.
 * @type {Array.<Menu>}
 */
Menu.instance = [];
