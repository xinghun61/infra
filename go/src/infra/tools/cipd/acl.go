// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"net/http"
	"time"

	"infra/libs/logging"
)

// PackageACLChangeAction defines a flavor of PackageACLChange.
type PackageACLChangeAction string

const (
	// GrantRole is used in PackageACLChange to request a role to be granted.
	GrantRole PackageACLChangeAction = "GRANT"
	// RevokeRole is used in PackageACLChange to request a role to be revoked.
	RevokeRole PackageACLChangeAction = "REVOKE"
)

// PackageACL is per package path per role access control list that is a part of
// larger overall ACL: ACL for package "a/b/c" is a union of PackageACLs for "a"
// "a/b" and "a/b/c".
type PackageACL struct {
	// PackagePath is a package subpath this ACL is defined for.
	PackagePath string
	// Role is a role that listed users have, e.g. 'READER', 'WRITER', ...
	Role string
	// Principals list users and groups granted the role.
	Principals []string
	// ModifiedBy specifies who modified the list the last time.
	ModifiedBy string
	// ModifiedTs is a timestamp when the list was modified the last time.
	ModifiedTs time.Time
}

// ACLOptions contains parameters shared by FetchACL and ModifyACL functions.
type ACLOptions struct {
	// ServiceURL is root URL of the backend service, or "" to use default service.
	ServiceURL string
	// Client is http.Client to use to make requests, default is http.DefaultClient.
	Client *http.Client
	// Log is a logger to use for logs, default is logging.DefaultLogger.
	Log logging.Logger
	// PackagePath is a package subpath to fetch or modify ACLs for.
	PackagePath string
}

// FetchACLOptions contains parameters for FetchACL function.
type FetchACLOptions struct {
	ACLOptions
}

// FetchACL returns a list of PackageACL objects (parent paths first) that
// together define access control list for given package subpath.
func FetchACL(options FetchACLOptions) ([]PackageACL, error) {
	// Fill in default options.
	if options.ServiceURL == "" {
		options.ServiceURL = DefaultServiceURL()
	}
	if options.Client == nil {
		options.Client = http.DefaultClient
	}
	if options.Log == nil {
		options.Log = logging.DefaultLogger
	}
	remote := newRemoteService(options.Client, options.ServiceURL, options.Log)
	return remote.fetchACL(options.PackagePath)
}

// PackageACLChange is a mutation to some package ACL.
type PackageACLChange struct {
	// Action defines what action to perform: GrantRole or RevokeRole.
	Action PackageACLChangeAction
	// Role to grant or revoke to a user or group.
	Role string
	// Principal is a user or a group to grant or revoke a role for.
	Principal string
}

// ModifyACLOptions contains parameters for ModifyACL function.
type ModifyACLOptions struct {
	ACLOptions

	// Changes defines changes to apply.
	Changes []PackageACLChange
}

// ModifyACL applies a set of PackageACLChanges to a package path.
func ModifyACL(options ModifyACLOptions) error {
	// Fill in default options.
	if options.ServiceURL == "" {
		options.ServiceURL = DefaultServiceURL()
	}
	if options.Client == nil {
		options.Client = http.DefaultClient
	}
	if options.Log == nil {
		options.Log = logging.DefaultLogger
	}
	remote := newRemoteService(options.Client, options.ServiceURL, options.Log)
	return remote.modifyACL(options.PackagePath, options.Changes)
}
