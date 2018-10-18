/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

// shape related classes

/** a point in 2 cartesian dimensions.
  * @constructor
  * @param x x-coord.
  * @param y y-coord.
  * @param opt_coordinateFrame a key that can be passed to a translation function to
  *   convert from one coordinate frame to another.
  *   Coordinate frames might correspond to things like windows, iframes, or
  *   any element with a position style attribute.
  */
function Point(x, y, opt_coordinateFrame) {
  /** a numeric x coordinate. */
  this.x = x;
  /** a numeric y coordinate. */
  this.y = y;
  /** a key that can be passed to a translation function to
    * convert from one coordinate frame to another.
    * Coordinate frames might correspond to things like windows, iframes, or
    * any element with a position style attribute.
    */
  this.coordinateFrame = opt_coordinateFrame || null;
}
Point.prototype.toString = function() {
  return '[P ' + this.x + ',' + this.y + ']';
};
Point.prototype.clone = function() {
  return new Point(this.x, this.y, this.coordinateFrame);
};

/** a distance between two points in 2-space in cartesian form.
  * A delta doesn't have a coordinate frame associated since all the coordinate
  * frames used in the HTML dom are convertible without rotation/scaling.
  * If a delta is not being used in pixel-space then it may be annotated with
  * a coordinate frame, and the undefined coordinate frame can be assumed
  * to represent pixel space.
  * @constructor
  * @param dx distance along x axis
  * @param dy distance along y axis
  */
function Delta(dx, dy) {
  /** a numeric distance along the x dimension. */
  this.dx = dx;
  /** a numeric distance along the y dimension. */
  this.dy = dy;
}
Delta.prototype.toString = function() {
  return '[D ' + this.dx + ',' + this.dy + ']';
};

/** a rectangle or bounding region.
  * @constructor
  * @param x x-coord of the left edge.
  * @param y y-coord of the top edge.
  * @param w width.
  * @param h height.
  * @param opt_coordinateFrame a key that can be passed to a translation function to
  *   convert from one coordinate frame to another.
  *   Coordinate frames might correspond to things like windows, iframes, or
  *   any element with a position style attribute.
  */
function Rect(x, y, w, h, opt_coordinateFrame) {
  /** the numeric x coordinate of the left edge. */
  this.x = x;
  /** the numeric y coordinate of the top edge. */
  this.y = y;
  /** the numeric distance between the right edge and the left. */
  this.w = w;
  /** the numeric distance between the top edge and the bottom. */
  this.h = h;
  /** a key that can be passed to a translation function to
    * convert from one coordinate frame to another.
    * Coordinate frames might correspond to things like windows, iframes, or
    * any element with a position style attribute.
    */
  this.coordinateFrame = opt_coordinateFrame || null;
}

/**
 * Determines whether the Rectangle contains the Point.
 * The Point is considered "contained" if it lies
 * on the boundary of, or in the interior of, the Rectangle.
 *
 * @param {Point} p
 * @return boolean indicating if this Rect contains p
 */
Rect.prototype.contains = function(p) {
  return this.x <= p.x && p.x < (this.x + this.w) &&
             this.y <= p.y && p.y < (this.y + this.h);
};

/**
 * Determines whether the given rectangle intersects this rectangle.
 *
 * @param {Rect} r
 * @return boolean indicating if this the two rectangles intersect
 */
Rect.prototype.intersects = function(r) {
  let p = function(x, y) {
    return new Point(x, y, null);
  };

  return this.contains(p(r.x, r.y)) ||
         this.contains(p(r.x + r.w, r.y)) ||
         this.contains(p(r.x + r.w, r.y + r.h)) ||
         this.contains(p(r.x, r.y + r.h)) ||
         r.contains(p(this.x, this.y)) ||
         r.contains(p(this.x + this.w, this.y)) ||
         r.contains(p(this.x + this.w, this.y + this.h)) ||
         r.contains(p(this.x, this.y + this.h));
};

Rect.prototype.toString = function() {
  return '[R ' + this.w + 'x' + this.h + '+' + this.x + '+' + this.y + ']';
};

Rect.prototype.clone = function() {
  return new Rect(this.x, this.y, this.w, this.h, this.coordinateFrame);
};
