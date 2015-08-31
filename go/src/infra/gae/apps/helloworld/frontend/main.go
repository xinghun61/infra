// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"net/http"

	"github.com/GoogleCloudPlatform/go-endpoints/endpoints"
	"github.com/luci/gae/impl/prod"
	"github.com/luci/gae/service/datastore"
	"golang.org/x/net/context"
	"google.golang.org/appengine/log"

	"infra/gae/epservice/example"
)

func init() {
	http.HandleFunc("/", handler)
	example.RegisterEndpointsService(endpoints.DefaultServer)
	endpoints.HandleHTTP()
}

func handler(w http.ResponseWriter, r *http.Request) {
	ctx := prod.UseRequest(r)
	count, err := registerVisitor(ctx)
	if err != nil {
		log.Errorf(ctx, "Failed: %s", err)
		count = -1
	}
	fmt.Fprintf(w, "Hello from frontend, you are visitor number %d!", count)
}

// Simple visitor counter, to show case how to use datastore (+ unit test).

type VisitorCounter struct {
	ID    string `gae:"$id"`
	Count int
}

func registerVisitor(ctx context.Context) (int, error) {
	counter := VisitorCounter{ID: "frontend"}
	err := datastore.Get(ctx).RunInTransaction(func(c context.Context) error {
		ds := datastore.Get(c)
		err := ds.Get(&counter)
		if err != nil && err != datastore.ErrNoSuchEntity {
			return err
		}
		counter.Count++
		return ds.Put(&counter)
	}, nil)
	return counter.Count, err
}
