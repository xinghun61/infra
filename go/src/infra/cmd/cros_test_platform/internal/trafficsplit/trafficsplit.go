// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package trafficsplit provides functionality to apply traffic splitter rules
// to test platform requests.
package trafficsplit

import (
	"github.com/golang/protobuf/proto"
	"go.chromium.org/chromiumos/infra/proto/go/chromiumos"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/migration/scheduler"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/errors"
)

// ApplyToRequest applies a scheduler traffic splitter config to a test platform
// request.
func ApplyToRequest(request *test_platform.Request, trafficSplitConfig *scheduler.TrafficSplit) (*steps.SchedulerTrafficSplitResponse, error) {
	if err := ensureSufficientForTrafficSplit(request); err != nil {
		return nil, errors.Annotate(err, "determine traffic split").Err()
	}

	rules := extractRulesRelevantToSuites(request.GetTestPlan().GetSuite(), trafficSplitConfig.SuiteOverrides)
	rules = NewRuleFilter(rules).ForRequest(request)
	if len(rules) == 0 {
		rules = NewRuleFilter(trafficSplitConfig.Rules).ForRequest(request)
	}

	var rule *scheduler.Rule
	switch {
	case len(rules) == 0:
		return nil, errors.Reason("no matching traffic split rule").Err()
	case len(rules) == 1:
		rule = rules[0]
	default:
		if err := ensureRulesAreCompatible(rules); err != nil {
			return nil, errors.Annotate(err, "determine traffic split").Err()
		}
		rule = rules[0]
	}
	return applyTrafficSplitRule(request, rule)
}

func ensureSufficientForTrafficSplit(r *test_platform.Request) error {
	if r.GetParams().GetScheduling().GetPool() == nil {
		return errors.Reason("request contains no pool information").Err()
	}
	return nil
}

func ensureRulesAreCompatible(rules []*scheduler.Rule) error {
	b := rules[0].GetBackend()
	s := rules[0].GetRequestMod().GetScheduling()
	for _, r := range rules[1:] {
		if r.GetBackend() != b {
			return errors.Reason("Rules %s and %s contain conflicting backends", rules[0], r).Err()
		}
		if schedulingNotEqual(s, r.GetRequestMod().GetScheduling()) {
			return errors.Reason("Rules %s and %s contain conflicting request modifications", rules[0], r).Err()
		}
	}
	return nil
}

func schedulingNotEqual(s1, s2 *test_platform.Request_Params_Scheduling) bool {
	if s1.GetUnmanagedPool() != s2.GetUnmanagedPool() {
		return true
	}
	if s1.GetManagedPool() != s2.GetManagedPool() {
		return true
	}
	if s1.GetQuotaAccount() != s2.GetQuotaAccount() {
		return true
	}
	return false
}

func applyTrafficSplitRule(request *test_platform.Request, rule *scheduler.Rule) (*steps.SchedulerTrafficSplitResponse, error) {
	newRequest := applyRequestModification(request, rule.GetRequestMod())
	switch rule.Backend {
	case scheduler.Backend_BACKEND_AUTOTEST:
		return &steps.SchedulerTrafficSplitResponse{
			AutotestRequest: newRequest,
		}, nil
	case scheduler.Backend_BACKEND_SKYLAB:
		return &steps.SchedulerTrafficSplitResponse{
			SkylabRequest: newRequest,
		}, nil
	default:
		return nil, errors.Reason("invalid backend %s in rule", rule.Backend.String()).Err()
	}
}

func applyRequestModification(request *test_platform.Request, mod *scheduler.RequestMod) *test_platform.Request {
	if mod == nil {
		return request
	}
	var dst test_platform.Request
	proto.Merge(&dst, request)
	if dst.Params == nil {
		dst.Params = &test_platform.Request_Params{}
	}
	proto.Merge(dst.Params.Scheduling, mod.Scheduling)
	return &dst
}

func extractRulesRelevantToSuites(suites []*test_platform.Request_Suite, suiteOverrides []*scheduler.SuiteOverride) []*scheduler.Rule {
	m := make(stringset.Set)
	for _, s := range suites {
		if s.GetName() != "" {
			m.Add(s.GetName())
		}
	}

	rules := []*scheduler.Rule{}
	for _, so := range suiteOverrides {
		if m.Has(so.GetSuite().GetName()) {
			rules = append(rules, so.Rule)
		}
	}
	return rules
}

// RuleFilter provides methods to get slices of rules filtered in various ways.
type RuleFilter []*scheduler.Rule

// NewRuleFilter returns a new RuleFilter.
func NewRuleFilter(rules []*scheduler.Rule) RuleFilter {
	return RuleFilter(rules)
}

// ForRequest returns rules relevant to a test platform request.
func (f RuleFilter) ForRequest(request *test_platform.Request) []*scheduler.Rule {
	ret := []*scheduler.Rule{}
	for _, r := range f {
		if isRuleRelevant(request, r) {
			ret = append(ret, r)
		}
	}
	return ret
}

func isRuleRelevant(request *test_platform.Request, rule *scheduler.Rule) bool {
	if isNonEmptyAndDistinct(
		request.GetParams().GetSoftwareAttributes().GetBuildTarget().GetName(),
		rule.GetRequest().GetBuildTarget().GetName(),
	) {
		return false
	}
	if isNonEmptyAndDistinct(
		request.GetParams().GetHardwareAttributes().GetModel(),
		rule.GetRequest().GetModel(),
	) {
		return false
	}
	return isSchedulingRelevant(request.GetParams().GetScheduling(), rule.GetRequest().GetScheduling())
}

func isSchedulingRelevant(got, want *test_platform.Request_Params_Scheduling) bool {
	if isNonEmptyAndDistinct(got.GetUnmanagedPool(), want.GetUnmanagedPool()) {
		return false
	}
	if isNonEmptyAndDistinct(got.GetManagedPool().String(), want.GetManagedPool().String()) {
		return false
	}
	if isNonEmptyAndDistinct(got.GetQuotaAccount(), want.GetQuotaAccount()) {
		return false
	}
	return true
}

func isNonEmptyAndDistinct(got, want string) bool {
	return got != "" && got != want
}

// ForModel returns rules relevant to a model.
func (f RuleFilter) ForModel(model string) []*scheduler.Rule {
	return f.ForRequest(&test_platform.Request{
		Params: &test_platform.Request_Params{
			HardwareAttributes: &test_platform.Request_Params_HardwareAttributes{
				Model: model,
			},
		},
	})
}

// ForBuildTarget returns rules relevant to a build target.
func (f RuleFilter) ForBuildTarget(buildTarget string) []*scheduler.Rule {
	return f.ForRequest(&test_platform.Request{
		Params: &test_platform.Request_Params{
			SoftwareAttributes: &test_platform.Request_Params_SoftwareAttributes{
				BuildTarget: &chromiumos.BuildTarget{
					Name: buildTarget,
				},
			},
		},
	})
}

// ForScheduling returns rules relevant to a scheduling argument.
func (f RuleFilter) ForScheduling(s *test_platform.Request_Params_Scheduling) []*scheduler.Rule {
	return f.ForRequest(&test_platform.Request{
		Params: &test_platform.Request_Params{
			Scheduling: s,
		},
	})
}
