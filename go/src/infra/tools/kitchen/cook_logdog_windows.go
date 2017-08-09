// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"fmt"
	"os"

	"golang.org/x/net/context"

	"go.chromium.org/luci/logdog/client/butler/streamserver"
)

// getLogDogStreamServerForPlatform returns a StreamServer instance usable on
// Windows builds.
func getLogDogStreamServerForPlatform(ctx context.Context, tdir string) (streamserver.StreamServer, error) {
	// Windows, use named pipe.
	return streamserver.NewNamedPipeServer(ctx, fmt.Sprintf("LUCILogDogKitchen_%d", os.Getpid()))
}
