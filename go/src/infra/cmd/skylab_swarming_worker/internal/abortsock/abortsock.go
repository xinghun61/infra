// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package abortsock implements abort sockets.

The abort socket is a SOCK_DGRAM Unix socket.  Any datagram sent to
this socket will be interpreted as a request to abort the job.

AbortSock.ListenForAbort will listen for a datagram on the abort
socket.  This is synchronous, so it should generally be called from a
goroutine.
*/
package abortsock

import (
	"context"
	"net"
	"os"
)

// AbortSock is used for receiving abort requests on a UNIX socket.
type AbortSock struct {
	// Path of socket file.
	Path string
	// Socket connection interface.
	net.PacketConn
}

// Open opens and returns an AbortSock.
// Make sure to defer Close on it.
func Open(path string) (*AbortSock, error) {
	c, err := net.ListenPacket("unixgram", path)
	if err != nil {
		return nil, err
	}
	return &AbortSock{Path: path, PacketConn: c}, nil
}

// AttachContext attaches a context to the abort socket.  When an abort
// is received, the context is canceled.
func (as *AbortSock) AttachContext(ctx context.Context) context.Context {
	ctx, f := context.WithCancel(ctx)
	go as.ListenForAbort(f)
	return ctx
}

// ListenForAbort synchronously waits for an abort request.  Any
// received datagram will be recognized as an abort request; the
// content of the datagram does not matter.
//
// When an abort request is received, ListenForAbort calls the
// function passed to it.
//
// If the AbortSock is closed, calls will return immediately.  f will
// be called.  To unblock a call to ListenForAbort, close the
// AbortSock.
func (as *AbortSock) ListenForAbort(f func()) {
	b := make([]byte, 16)
	_, _, _ = as.ReadFrom(b)
	// ReadFrom returns an error only if the socket is closed or a
	// timeout is set, so we can interpret it as an
	// abort/cancellation.
	f()
}

// Close the abort socket.
func (as *AbortSock) Close() error {
	_ = as.PacketConn.Close()
	return os.Remove(as.Path)
}

// Abort sends an abort datagram to the socket at the given path.
func Abort(path string) error {
	c, err := net.Dial("unixgram", path)
	if err != nil {
		return err
	}
	// The value sent does not matter.
	b := []byte("abort")
	_, err = c.Write(b)
	return err
}
