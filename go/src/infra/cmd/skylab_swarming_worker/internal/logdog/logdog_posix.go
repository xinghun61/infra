// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build darwin linux

package logdog

import (
	"context"
	"io"
	"log"
	"os"
	"time"

	"github.com/pkg/errors"
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/logdog/client/annotee"
	"go.chromium.org/luci/logdog/client/annotee/annotation"
	"go.chromium.org/luci/logdog/client/butler"
	"go.chromium.org/luci/logdog/client/butler/output"
	"go.chromium.org/luci/logdog/client/butler/output/logdog"
	"go.chromium.org/luci/logdog/client/butlerlib/streamclient"
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

	// butler
	c.butler, err = newButler(ctx, o, c.output)
	if err != nil {
		return nil, errors.Wrap(err, "make butler")
	}

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
	ch := make(chan struct{})
	c.processorFinished = ch
	// This goroutine terminates when the write pipe is closed.
	go func() {
		if err := c.processor.RunStreams(streams); err != nil {
			log.Printf("Error writing logdog streams: %s", err)
		}
		close(ch)
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
		Client:                 streamclient.NewLoopback(b, ""),
		Execution:              annotation.ProbeExecution(os.Args, nil, ""),
		MetadataUpdateInterval: 30 * time.Second,
		Offline:                false,
		CloseSteps:             true,
	}
	return annotee.New(ctx, o)
}
