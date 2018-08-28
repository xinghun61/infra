// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build darwin linux

package logdog

import (
	"context"
	"io"
	"io/ioutil"
	"log"
	"path/filepath"

	"github.com/pkg/errors"
	"go.chromium.org/luci/logdog/client/annotee"
	"go.chromium.org/luci/logdog/client/butler/streamserver"
	"go.chromium.org/luci/lucictx"
)

// New initializes a Client according to the Options.
func New(ctx context.Context, o *Options) (c *Client, err error) {
	c = &Client{}
	defer func(c *Client) {
		if err != nil {
			c.Close()
		}
	}(c)

	ctx, err = lucictx.SwitchLocalAccount(ctx, "system")
	if err != nil {
		return nil, errors.Wrap(err, "switch LUCI local account")
	}

	// output
	a := newAuthenticator(ctx)
	c.output, err = newOutput(ctx, o, a)
	if err != nil {
		return nil, errors.Wrap(err, "make logdog output")
	}

	// stream server
	c.tempDir, err = ioutil.TempDir("", "logdog-stream-server")
	if err != nil {
		return nil, errors.Wrap(err, "make streamserver tempdir")
	}
	s, err := streamserver.NewUNIXDomainSocketServer(ctx, filepath.Join(c.tempDir, "ld.sock"))
	if err != nil {
		return nil, errors.Wrap(err, "make logdog stream server")
	}
	// The StreamServer needs to be closed after s.Listen
	// succeeds.  However, AddStreamServer will arrange for the
	// StreamServer to be closed separately.  If the StreamServer
	// is closed a second time, it will panic.
	if err := s.Listen(); err != nil {
		return nil, errors.Wrap(err, "start streamserver listen")
	}
	defer func() {
		if s != nil {
			s.Close()
		}
	}()

	// butler
	c.butler, err = newButler(ctx, o, c.output)
	if err != nil {
		return nil, errors.Wrap(err, "make butler")
	}
	c.butler.AddStreamServer(s)
	// Clear StreamServer variable so we don't close it.
	s = nil

	// annotee processor
	c.processor = newProcessor(ctx, c.butler, "")

	// streams
	c.readPipe, c.writePipe = io.Pipe()
	streams := []*annotee.Stream{
		{
			Reader:   c.readPipe,
			Name:     annotee.STDOUT,
			Annotate: true,
		},
	}
	// This goroutine terminates when the write pipe is closed.
	go func() {
		if err := c.processor.RunStreams(streams); err != nil {
			log.Printf("Error writing logdog streams: %s", err)
		}
	}()
	return c, nil
}
