// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

// +build darwin dragonfly freebsd linux netbsd openbsd

package main

import (
	"path/filepath"

	"golang.org/x/net/context"

	"go.chromium.org/luci/logdog/client/butler/streamserver"
)

// getLogDogStreamServerForPlatform returns a StreamServer instance usable on
// POSIX builds.
func getLogDogStreamServerForPlatform(ctx context.Context, tdir string) (streamserver.StreamServer, error) {
	// POSIX, use UNIX domain socket.
	return streamserver.NewUNIXDomainSocketServer(ctx, filepath.Join(tdir, "ld.sock"))
}
