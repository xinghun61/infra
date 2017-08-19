// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

//go:generate go install infra/cmd/bqexport
//go:generate bqexport -name CompletedBuildLegacy -out-dir ../../../tools/bqschemaupdater
//go:generate bqexport -name CompletedStepLegacy -out-dir ../../../tools/bqschemaupdater

package buildevent
