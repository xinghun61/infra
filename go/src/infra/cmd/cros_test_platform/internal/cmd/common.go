// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"net/http"
	"os"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
)

var (
	unmarshaller = jsonpb.Unmarshaler{AllowUnknownFields: true}
	marshaller   = jsonpb.Marshaler{}
)

func newAuthenticatedTransport(ctx context.Context, f *authcli.Flags) (http.RoundTripper, error) {
	o, err := f.Options()
	if err != nil {
		return nil, errors.Annotate(err, "create authenticated transport").Err()
	}
	a := auth.NewAuthenticator(ctx, auth.SilentLogin, o)
	return a.Transport()
}

func newAuthenticatedHTTPClient(ctx context.Context, f *authcli.Flags) (*http.Client, error) {
	t, err := newAuthenticatedTransport(ctx, f)
	if err != nil {
		return nil, err
	}
	return &http.Client{Transport: t}, nil
}

func readRequest(inFile string, request proto.Message) error {
	r, err := os.Open(inFile)
	if err != nil {
		return errors.Annotate(err, "read request").Err()
	}
	defer r.Close()
	if err := unmarshaller.Unmarshal(r, request); err != nil {
		return errors.Annotate(err, "read request").Err()
	}
	return nil
}

// exitCode computes the exit code for this tool.
func exitCode(err error) int {
	switch {
	case err == nil:
		return 0
	case partialErrorTag.In(err):
		return 2
	default:
		return 1
	}
}

// writeResponseWithError writes response as JSON encoded protobuf to outFile.
//
// If errorSoFar is non-nil, this function considers the response to be partial
// and tags the returned error to that effect.
func writeResponseWithError(outFile string, response proto.Message, errorSoFar error) error {
	w, err := os.Create(outFile)
	if err != nil {
		return errors.MultiError{errorSoFar, errors.Annotate(err, "write response").Err()}
	}
	defer w.Close()
	if err := marshaller.Marshal(w, response); err != nil {
		return errors.MultiError{errorSoFar, errors.Annotate(err, "write response").Err()}
	}
	return partialErrorTag.Apply(errorSoFar)
}

// writeResponseWithError writes response as JSON encoded protobuf to outFile.
func writeResponse(outFile string, response proto.Message) error {
	return writeResponseWithError(outFile, response, nil)
}

// Use partialErrorTag to indicate when partial response is written to the
// output file. Use returnCode() to return the corresponding return code on
// process exit.
var partialErrorTag = errors.BoolTag{Key: errors.NewTagKey("partial results are available despite this error")}

func setupLogging(ctx context.Context) context.Context {
	return logging.SetLevel(ctx, logging.Debug)
}
