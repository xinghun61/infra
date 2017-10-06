// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

//go:generate go install infra/cmd/bqexport
//go:generate bqexport -name TestResultEvent -path ../../../tools/bqschemaupdater/flakiness/test_results.pb.txt
