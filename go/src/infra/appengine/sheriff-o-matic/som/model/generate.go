// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

//go:generate go install infra/cmd/bqexport
//go:generate bqexport -name SOMAlertsEvent -path ../../../../tools/bqschemaupdater/raw_events/som_alerts.pb.txt
