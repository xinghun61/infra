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
	"os"
	"path/filepath"
	"time"

	"github.com/pkg/errors"
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/logdog/client/annotee"
	"go.chromium.org/luci/logdog/client/annotee/annotation"
	"go.chromium.org/luci/logdog/client/butler"
	"go.chromium.org/luci/logdog/client/butler/output"
	"go.chromium.org/luci/logdog/client/butler/output/logdog"
	"go.chromium.org/luci/logdog/client/butler/streamserver"
	"go.chromium.org/luci/logdog/client/butler/streamserver/localclient"
	"go.chromium.org/luci/logdog/common/types"
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

func newAuthenticator(ctx context.Context) *auth.Authenticator {
	o := auth.Options{
		Method: auth.LUCIContextMethod,
		Scopes: []string{
			auth.OAuthScopeEmail,
			"https://www.googleapis.com/auth/cloud-platform",
		},
	}
	return auth.NewAuthenticator(ctx, auth.SilentLogin, o)
}

func newOutput(ctx context.Context, o *Options, a *auth.Authenticator) (output.Output, error) {
	prefix, _ := o.AnnotationStream.Path.Split()
	c := logdog.Config{
		Auth:       a,
		Host:       o.AnnotationStream.Host,
		Project:    o.AnnotationStream.Project,
		Prefix:     prefix,
		SourceInfo: o.SourceInfo,
		RPCTimeout: 30 * time.Second,
	}
	out, err := c.Register(ctx)
	if err != nil {
		return nil, err
	}
	return out, nil
}

func newButler(ctx context.Context, o *Options, out output.Output) (*butler.Butler, error) {
	prefix, _ := o.AnnotationStream.Path.Split()
	c := butler.Config{
		Output:     out,
		Project:    o.AnnotationStream.Project,
		Prefix:     prefix,
		BufferLogs: true,
	}
	b, err := butler.New(ctx, c)
	if err != nil {
		return nil, err
	}
	return b, nil
}

func newProcessor(ctx context.Context, b *butler.Butler, basePath string) *annotee.Processor {
	o := annotee.Options{
		Base:                   types.StreamName(basePath),
		Client:                 localclient.New(b),
		Execution:              annotation.ProbeExecution(os.Args, nil, ""),
		MetadataUpdateInterval: 30 * time.Second,
		Offline:                false,
		CloseSteps:             true,
	}
	return annotee.New(ctx, o)
}
