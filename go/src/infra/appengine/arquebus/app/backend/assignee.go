// Copyright 2019 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package backend

import (
	"context"

	"infra/appengine/arquebus/app/backend/model"
	"infra/monorailv2/api/api_proto"
)

func findAssigneeAndCCs(c context.Context, assigner *model.Assigner) (assignee *monorail.UserRef, ccs []*monorail.UserRef, err error) {
	// TODO(crbug/849469): implement me
	return nil, nil, nil
}
