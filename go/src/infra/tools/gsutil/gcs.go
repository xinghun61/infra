// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"context"
	"fmt"
	"net/url"
	"os"
	"strings"

	"cloud.google.com/go/storage"

	"go.chromium.org/luci/auth"

	"google.golang.org/api/option"
)

func parseURL(path string) (bucket string, object string, err error) {
	var urlObj *url.URL
	urlObj, err = url.Parse(path)
	if err != nil {
		return
	}
	if urlObj.Scheme != "gs" {
		err = fmt.Errorf("URL %q must begin with \"gs://\"", path)
		return
	}
	bucket = urlObj.Host
	object = strings.TrimPrefix(urlObj.Path, "/")
	return
}

// Creates a Cloud Storage client given auth options. Note, the scopes that the client has
// access to are determined by authDefaults.Scopes in main.go.
func storageClient(ctx context.Context, authOpts auth.Options) (*storage.Client, error) {
	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	tokenSource, err := authenticator.TokenSource()
	if err == auth.ErrLoginRequired {
		fmt.Fprintln(os.Stderr, "Login required: run `gsutil auth-login`.")
		os.Exit(1)
	} else if err != nil {
		return nil, err
	}
	return storage.NewClient(ctx, option.WithTokenSource(tokenSource))
}

func object(client *storage.Client, url string) (*storage.ObjectHandle, error) {
	bucketName, objectName, err := parseURL(url)
	if err != nil {
		return nil, err
	}
	return client.Bucket(bucketName).Object(objectName), nil
}
