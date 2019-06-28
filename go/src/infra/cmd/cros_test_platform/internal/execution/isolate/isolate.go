// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package isolate defines an interface for interacting with isolate.
package isolate

// Client defines and interface used to interact with an isolate service.
type Client interface {
	// TODO(akeshet): Flesh out this interface with the actual necessary
	// methods.
}

type nullClient struct{}

// NullClient is a fake implementation of Client which does nothing.
var NullClient Client = &nullClient{}
