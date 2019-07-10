// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package isolate provides an interface for fetching files from isolate.
package isolate

import (
	"context"

	"go.chromium.org/luci/common/isolated"
)

// Getter is an interface for fetching a file from isolate.
type Getter interface {
	GetFile(ctx context.Context, digest isolated.HexDigest, filePath string) ([]byte, error)
}

// GetterFactory is a function that returns a Getter for a given server.
type GetterFactory func(ctx context.Context, server string) (Getter, error)
