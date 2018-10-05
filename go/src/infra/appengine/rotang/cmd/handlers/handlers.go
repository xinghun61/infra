// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"infra/appengine/rotang"
	"infra/appengine/rotang/pkg/algo"

	"golang.org/x/net/context"
	"golang.org/x/oauth2"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// State holds shared state between handlers.
type State struct {
	selfURL     string
	prodENV     string
	calendar    rotang.Calenderer
	generators  *algo.Generators
	memberStore func(context.Context) rotang.MemberStorer
	oauthConfig *oauth2.Config
	token       *oauth2.Token
	shiftStore  func(context.Context) rotang.ShiftStorer
	configStore func(context.Context) rotang.ConfigStorer
	mailAddress string
	mailSender  rotang.MailSender
}

// Options contains the options used by the handlers.
type Options struct {
	URL         string
	ProdENV     string
	Calendar    rotang.Calenderer
	Generators  *algo.Generators
	MailSender  rotang.MailSender
	MailAddress string

	MemberStore func(context.Context) rotang.MemberStorer
	ConfigStore func(context.Context) rotang.ConfigStorer
	ShiftStore  func(context.Context) rotang.ShiftStorer
}

// New creates a new handlers State container.
func New(opt *Options) (*State, error) {
	switch {
	case opt == nil:
		return nil, status.Errorf(codes.InvalidArgument, "opt can not be nil")
	case opt.ProdENV == "":
		return nil, status.Errorf(codes.InvalidArgument, "ProdENV must be set")
	case opt.URL == "":
		return nil, status.Errorf(codes.InvalidArgument, "URL must be set")
	case opt.Calendar == nil:
		return nil, status.Errorf(codes.InvalidArgument, "Calendar can not be nil")
	case opt.Generators == nil:
		return nil, status.Errorf(codes.InvalidArgument, "Genarators can not be nil")
	case opt.MemberStore == nil, opt.ShiftStore == nil, opt.ConfigStore == nil:
		return nil, status.Errorf(codes.InvalidArgument, "Store functions can not be nil")
	}
	return &State{
		prodENV:     opt.ProdENV,
		selfURL:     opt.URL,
		calendar:    opt.Calendar,
		generators:  opt.Generators,
		memberStore: opt.MemberStore,
		shiftStore:  opt.ShiftStore,
		configStore: opt.ConfigStore,
		mailSender:  opt.MailSender,
		mailAddress: opt.MailAddress,
	}, nil
}

// IsProduction is true if the service is running in production.
func (h *State) IsProduction() bool {
	return h.prodENV == "production"
}

// IsStaging is true if the service is running in staging.
func (h *State) IsStaging() bool {
	return h.prodENV == "staging"
}

// IsLocal is true if the service is running in the local dev environment.
func (h *State) IsLocal() bool {
	return h.prodENV == "local"
}
