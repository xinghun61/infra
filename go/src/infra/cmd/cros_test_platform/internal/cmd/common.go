// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"net/http"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/errors"
)

const (
	// failedWithoutResponse is returned by a script that failed without
	// producing a response.
	failedWithoutResponse = 1

	// retcodeFailedWithoutResponse is returned by a script that failed but
	// nevertheless produced a response.
	failedWithResponse = 2
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
