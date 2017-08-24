// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

//go:generate go install infra/cmd/bqexport
//go:generate bqexport -path ../../../tools/bqschemaupdater/raw_events/buildevent_completed_build_legacy.json
//go:generate bqexport -path ../../../tools/bqschemaupdater/raw_events/buildevent_completed_step_legacy.json

package buildevent
