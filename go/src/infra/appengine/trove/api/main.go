// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"

	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	_ "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaemiddleware/flex"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/grpc/discovery"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"

	pb "infra/appengine/trove/api/testresults"
	// TODO: github.com/luci/luci-go/grpc/grpcmon
)

var (
	serverAddr = flag.String("server", ":8080", "The server address")
)

func getAuthClient(ctx context.Context) (*http.Client, error) {
	t, err := auth.GetRPCTransport(ctx, auth.AsSelf)
	if err != nil {
		return nil, err
	}
	return &http.Client{Transport: t}, nil
}

type apiServer struct{}

func (s *apiServer) Collect(ctx context.Context, req *pb.CollectTestResultsRequest) (*pb.CollectTestResultsResponse, error) {
	_, err := getAuthClient(ctx)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "couldn't create auth client: %v", err)
	}

	return nil, fmt.Errorf("not implemented")
}

func main() {
	flag.Parse()
	ctx := gologger.StdConfig.Use(context.Background())
	ctx = flex.WithGlobal(ctx)

	r := router.NewWithRootContext(ctx)

	flex.ReadOnlyFlex.InstallHandlers(r)
	middleware := flex.ReadOnlyFlex.Base()

	apiSvc := &apiServer{}
	var server prpc.Server
	pb.RegisterTestResultsServer(&server, apiSvc)
	discovery.Enable(&server)

	server.InstallHandlers(r, middleware)

	http.DefaultServeMux.Handle("/", r)

	log.Printf("Server starting\n")
	log.Fatal(http.ListenAndServe(*serverAddr, nil))
}
