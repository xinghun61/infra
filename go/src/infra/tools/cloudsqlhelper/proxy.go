// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
)

const cloudSQLProxy = "cloud_sql_proxy"

// CheckCloudSQLProxy returns nil if 'cloud_sql_proxy' binary is in PATH.
func CheckCloudSQLProxy() error {
	_, err := exec.LookPath(cloudSQLProxy)
	if err != nil {
		return fmt.Errorf("can't locate cloud_sql_proxy in path, see https://cloud.google.com/sql/docs/mysql/connect-admin-proxy#install")
	}
	return nil
}

// WithLocalDBSocket optionally launches cloud_sql_proxy and calls a function.
func WithLocalDBSocket(ctx context.Context, dbConf *DBConfig, body func(ctx context.Context, socket string) error) error {
	// Skip the proxy if not using Cloud SQL. The local socket path should be
	// configured in this case.
	if dbConf.CloudSQLInstance == "" {
		if dbConf.LocalSocket == "" {
			return fmt.Errorf("bad config - 'local_socket' is required if 'cloud_sql_instance' is not set")
		}
		return body(ctx, dbConf.LocalSocket)
	}

	// Make sure the proxy is installed in PATH.
	if err := CheckCloudSQLProxy(); err != nil {
		return err
	}

	socketPath := ""
	if dbConf.LocalSocket != "" {
		if !strings.HasSuffix(dbConf.LocalSocket, dbConf.CloudSQLInstance) {
			return fmt.Errorf("local socket path %q must end in %q", dbConf.LocalSocket, dbConf.CloudSQLInstance)
		}
		socketPath = dbConf.LocalSocket
	} else {
		// The length of path for unix domain sockets is limited at ~100. So we pick
		// a short directory path to store them in. Note that os.TempDir() returns
		// huge path on OSX, since it resolves symlinks, so we hardcode the path
		// instead.
		//
		// See https://serverfault.com/a/641388 for socket path size limits.
		//
		// We also use unique socket dir per PID, to avoid conflicts if multiple
		// copies of cloudsqlhelper are running. And finally, we must append
		// fully qualified Cloud SQL instance name to the end, since cloud_sql_proxy
		// always does that :(
		socketPath = fmt.Sprintf("/var/tmp/csql/%d/%s/%s", os.Getpid(), dbConf.ID, dbConf.CloudSQLInstance)
	}

	// Friendly warning to avoid great confusion.
	if len(socketPath) > 100 {
		logging.Warningf(ctx, "Path length to the socket file is too large, there may be problems: %s", socketPath)
	}

	// Cleanup stale socket files. If the socket file is actually alive, just use
	// it, assuming it is connected to the correct proxy. This happens often in
	// real life, when there's a proxy connection open in separate terminal.
	if _, err := os.Stat(socketPath); err == nil {
		if canDial(socketPath) {
			return body(ctx, socketPath) // alive, use it
		}
		os.Remove(socketPath) // stale, kill it
	}

	// Create the directory for the socket if doesn't exit. Clean it up later if
	// we indeed created it.
	socketDir := filepath.Dir(socketPath)
	if _, err := os.Stat(socketDir); os.IsNotExist(err) {
		if err := os.MkdirAll(socketDir, 0700); err != nil {
			return err
		}
		defer os.RemoveAll(socketDir)
	}

	// Use a subcontext to kill the process when exiting the function.
	ctx, cancel := context.WithCancel(ctx)
	cmd := exec.CommandContext(ctx, cloudSQLProxy, "-instances", dbConf.CloudSQLInstance, "-dir", socketDir)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	defer func() {
		cancel()   // kill the process
		cmd.Wait() // wait until it is really dead
	}()

	if err := cmd.Start(); err != nil {
		logging.Errorf(ctx, "Failed to start cloud_sql_proxy - %s", err)
		return err
	}

	// Busy-loop until the file socket appears (usually this is instantaneous).
	deadline := clock.Now(ctx).Add(5 * time.Second)
	for {
		if _, err := os.Stat(socketPath); err == nil {
			break // found!
		}
		if clock.Now(ctx).After(deadline) {
			logging.Errorf(ctx, "Timeout when waiting for cloud_sql_proxy socket %q", socketPath)
			return fmt.Errorf("timeout while waiting for cloud_sql_proxy")
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-clock.After(ctx, 50*time.Millisecond):
		}
	}

	return body(ctx, socketPath)
}

// canDial returns true if somebody is listening to the unix socket.
func canDial(socket string) bool {
	c, err := net.Dial("unix", socket)
	if c != nil {
		c.Close()
	}
	return err == nil
}
