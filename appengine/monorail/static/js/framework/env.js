/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * @fileoverview Defines the type of the CS_env Javascript object
 * provided by the Codesite server.
 *
 * This is marked as an externs file so that any variable defined with a
 * CS.env type will not have its properties renamed.
 * @externs
 */

/** Codesite namespace object. */
var CS = {};

/**
 * Javascript object holding basic information about the current page.
 * This is defined as an interface so that we can use CS.env as a Closure
 * type name, but it will never be implemented; rather, it will be
 * made available on every page as the global object CS_env (see
 * codesite/templates/demetrius/master-header.ezt).
 *
 * The type of the CS_env global object will actually be one of
 * CS.env, CS.project_env, etc. depending on the page
 * rendered by the server.
 *
 * @interface
 */
CS.env = function() {};

/**
 * Like relativeBaseUrl, but a full URL preceded by http://code.google.com
 * @type {string}
 */
CS.env.prototype.absoluteBaseUrl;

/**
 * Path to versioned static assets (mostly js and css).
 * @type {string}
 */
CS.env.prototype.appVersion;

/**
 * Request token for the logged-in user, or null for the anonymous user.
 * @type {?string}
 */
CS.env.prototype.token;

/**
 * Email address of the logged-in user, or null for anon.
 * @type {?string}
 */
CS.env.prototype.loggedInUserEmail;

/**
 * Url to the logged-in user's profile, or null for anon.
 * @type {?string}
 */
CS.env.prototype.profileUrl;

/**
 * CS.env specialization for browsing project pages.
 * @interface
 * @extends {CS.env}
 */
CS.project_env = function() {};

/** @type {string} */
CS.project_env.prototype.projectName;
