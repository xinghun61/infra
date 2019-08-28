// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package tokman implements an OAuth access token file manager.
package tokman

import (
	"context"
	"encoding/json"
	"log"
	"math/rand"
	"os"
	"time"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/common/errors"
	"golang.org/x/oauth2"
)

const (
	defaultLifetime = 10 * time.Minute
)

// Renewer is used to renew an access token file.
type Renewer struct {
	a    *auth.Authenticator
	path string
}

// Make makes an access token file and returns a Renewer for renewing
// the token.
func Make(a *auth.Authenticator, path string, lifetime time.Duration) (Renewer, error) {
	r := Renewer{
		a:    a,
		path: path,
	}
	if _, err := r.RenewOnce(lifetime); err != nil {
		return Renewer{}, errors.Annotate(err, "make access token file").Err()
	}
	return r, nil
}

// KeepNew keeps the access token valid until the context is canceled.
// This function blocks until canceled.
func (r Renewer) KeepNew(ctx context.Context) {
	d := newDelayer()
	for ctx.Err() == nil {
		tok, err := r.RenewOnce(defaultLifetime)
		if err != nil {
			log.Printf("Error: %s", err)
			sleep(ctx, d.Next())
			continue
		}
		d.Reset()
		sleep(ctx, tok.Expiry.Sub(time.Now())-time.Second)
	}
}

// sleep provides cancelable sleep.
func sleep(ctx context.Context, d time.Duration) {
	select {
	case <-ctx.Done():
	case <-time.After(d):
	}
}

// RenewOnce renews the access token file once.
func (r Renewer) RenewOnce(lifetime time.Duration) (*oauth2.Token, error) {
	tok, err := r.a.GetAccessToken(lifetime)
	if err != nil {
		return nil, errors.Annotate(err, "renew access token file").Err()
	}
	if err := writeToken(tok, r.path); err != nil {
		return nil, errors.Annotate(err, "renew access token file").Err()
	}
	return tok, nil
}

// writeToken atomically writes the OAuth2 token to the JSON file used
// by Swarming bots.
func writeToken(t *oauth2.Token, path string) error {
	tmp := path + ".tmp"
	f, err := os.Create(tmp)
	if err != nil {
		return errors.Annotate(err, "write token").Err()
	}
	defer f.Close()
	data := struct {
		Token  string `json:"token"`
		Expiry int64  `json:"expiry"`
	}{t.AccessToken, t.Expiry.Unix()}
	e := json.NewEncoder(f)
	if err := e.Encode(data); err != nil {
		return errors.Annotate(err, "write token").Err()
	}
	if err := f.Close(); err != nil {
		return errors.Annotate(err, "write token").Err()
	}
	if err := os.Rename(tmp, path); err != nil {
		return errors.Annotate(err, "write token").Err()
	}
	return nil
}

type rander interface {
	// Float32 is as implemented by rand.Rand
	Float32() float32
}

// errDelayer calculates how much to wait between retries.  This
// implements a bounded exponential backoff with random jitter.
type errDelayer struct {
	last   time.Duration
	rander rander
}

func newDelayer() *errDelayer {
	return &errDelayer{
		rander: rand.New(rand.NewSource(time.Now().UnixNano())),
	}
}

func (d *errDelayer) Next() time.Duration {
	if d.last > 0 {
		d.last *= 2
	} else {
		d.last = 20 * time.Millisecond
	}
	jitter := randRange(d.rander, float32(d.last/10))
	return d.last + time.Duration(jitter)
}

func (d *errDelayer) Reset() {
	d.last = 0
}

// randRange returns a random value between -x and +x.
func randRange(r rander, x float32) float32 {
	return x*2*r.Float32() - x
}
