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
	a := auth.NewAuthenticator(ctx, auth.OptionalLogin, o)
	return a.Transport()
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

// writeResponse writes response as JSON encoded protobuf to outFile.
//
// If errorSoFar is non-nil, this function considers the response to be partial
// and tags the returned error to that effect.
func writeResponse(outFile string, response proto.Message, errorSoFar error) error {
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

// Use partialErrorTag to indicate when partial response is written to the
// output file. Use returnCode() to return the corresponding return code on
// process exit.
var partialErrorTag = errors.BoolTag{Key: errors.NewTagKey("partial results are available despite this error")}
