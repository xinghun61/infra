/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * Functions used by Monorail to control drag-and-drop re-orderable lists
 *
 */

/**
 * Initializes the drag-and-drop functionality on the elements of a
 * container node.
 * TODO(lukasperaza): allow bulk drag-and-drop
 * @param {Element} container The HTML container element to turn into
 *    a drag-and-drop list. The items of the list must have the
 *    class 'drag_item'
 */
function TKR_initDragAndDrop(container, opt_onDrop, opt_preventMultiple) {
  let dragSrc = null;
  let dragLocation = null;
  let dragItems = container.getElementsByClassName('drag_item');
  let target = null;

  opt_preventMultiple = opt_preventMultiple || false;
  opt_onDrop = opt_onDrop || function() {};

  function _handleMouseDown(event) {
    target = event.target;
  }

  function _handleDragStart(event) {
    let el = event.currentTarget;
    let gripper = el.getElementsByClassName('gripper');
    if (gripper.length && !gripper[0].contains(target)) {
      event.preventDefault();
      return;
    }
    el.style.opacity = 0.4;
    event.dataTransfer.setData('text/html', el.outerHTML);
    event.dataTransfer.dropEffect = 'move';
    dragSrc = el;
  }

  function inRect(rect, x, y) {
    if (x < rect.left || x > rect.right) {
      return '';
    } else if (rect.top <= y && y <= rect.top + rect.height / 2) {
      return 'top';
    } else {
      return 'bottom';
    }
  }

  function _handleDragOver(event) {
    if (dragSrc == null) {
      return true;
    }
    event.preventDefault();
    let el = event.currentTarget;
    let rect = el.getBoundingClientRect(),
      classes = el.classList;
    let section = inRect(rect, event.clientX, event.clientY);
    if (section == 'top' && !classes.contains('top')) {
      dragLocation = 'top';
      classes.remove('bottom');
      classes.add('top');
    } else if (section == 'bottom' && !classes.contains('bottom')) {
      dragLocation = 'bottom';
      classes.remove('top');
      classes.add('bottom');
    }
    return false;
  }

  function removeClasses(el) {
    el.classList.remove('top');
    el.classList.remove('bottom');
  }

  function _handleDragDrop(event) {
    let el = event.currentTarget;
    if (dragSrc == null || el == dragSrc) {
      return true;
    }

    if (opt_preventMultiple) {
      let dragItems = container.getElementsByClassName('drag_item');
      for (let i = 0; i < dragItems.length; i++) {
        dragItems[i].setAttribute('draggable', false);
      }
    }

    let srcID = dragSrc.getAttribute('data-id');
    let id = el.getAttribute('data-id');

    if (dragLocation == 'top') {
      el.parentNode.insertBefore(dragSrc, el);
      opt_onDrop(srcID, id, 'above');
    } else if (dragLocation == 'bottom') {
      el.parentNode.insertBefore(dragSrc, el.nextSibling);
      opt_onDrop(srcID, id, 'below');
    }
    dragSrc.style.opacity = 0.4;
    dragSrc = null;
  }

  function _handleDragEnd(event) {
    if (dragSrc) {
      dragSrc.style.opacity = 1;
      dragSrc = null;
    }
    for (let i = 0; i < dragItems.length; i++) {
      removeClasses(dragItems[i]);
    }
  }

  for (let i = 0; i < dragItems.length; i++) {
    let el = dragItems[i];
    el.setAttribute('draggable', true);
    el.addEventListener('mousedown', _handleMouseDown);
    el.addEventListener('dragstart', _handleDragStart);
    el.addEventListener('dragover', _handleDragOver);
    el.addEventListener('drop', _handleDragDrop);
    el.addEventListener('dragend', _handleDragEnd);
    el.addEventListener('dragleave', function(event) {
      removeClasses(event.currentTarget);
    });
  }
}
