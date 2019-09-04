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

package frontend

import (
	"time"

	"github.com/golang/protobuf/ptypes"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"

	"infra/appengine/drone-queen/api"
	"infra/appengine/drone-queen/internal/config"
	"infra/appengine/drone-queen/internal/entities"
	"infra/appengine/drone-queen/internal/queries"
)

// DroneQueenImpl implements service interfaces.
type DroneQueenImpl struct {
	nowFunc func() time.Time
}

// ReportDrone implements service interfaces.
func (q *DroneQueenImpl) ReportDrone(ctx context.Context, req *api.ReportDroneRequest) (res *api.ReportDroneResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	res = &api.ReportDroneResponse{
		Status: api.ReportDroneResponse_OK,
	}
	id := entities.DroneID(req.GetDroneUuid())
	// Assign a new UUID if needed.
	if id == "" {
		id, err = queries.CreateNewDrone(ctx, q.now())
		if err != nil {
			return nil, err
		}
		res.DroneUuid = string(id)
	}
	// Refresh expiration time.
	d := entities.Drone{ID: id}
	f := func(ctx context.Context) error {
		if err = datastore.Get(ctx, &d); err != nil {
			if datastore.IsErrNoSuchEntity(err) {
				res.Status = api.ReportDroneResponse_UNKNOWN_UUID
			}
			return errors.Annotate(err, "get drone %s", id).Err()
		}
		if q.now().After(d.Expiration) {
			res.Status = api.ReportDroneResponse_UNKNOWN_UUID
			return errors.Reason("drone expired").Err()
		}
		d.Expiration = q.now().Add(config.AssignmentDuration(ctx)).UTC()
		if err = datastore.Put(ctx, &d); err != nil {
			return errors.Annotate(err, "refresh drone expiration").Err()
		}
		return nil
	}
	if err = datastore.RunInTransaction(ctx, f, nil); err != nil {
		// Specially handle specific status errors if they
		// were set.  These need to be reported in a regular
		// response.
		if res.Status != api.ReportDroneResponse_OK {
			return res, nil
		}
		return nil, err
	}
	// Assign new DUTs.
	var duts []*entities.DUT
	f = func(ctx context.Context) error {
		duts, err = queries.AssignNewDUTs(ctx, id, req.GetLoadIndicators())
		return err
	}
	if err = datastore.RunInTransaction(ctx, f, nil); err != nil {
		return nil, err
	}
	// Populate response fields.
	res.ExpirationTime, err = ptypes.TimestampProto(d.Expiration)
	if err != nil {
		// Input time should always be valid.
		panic(err)
	}
	for _, d := range duts {
		if d.AssignedDrone != id {
			panic(d)
		}
		res.AssignedDuts = append(res.AssignedDuts, string(d.ID))
		if d.Draining {
			res.DrainingDuts = append(res.DrainingDuts, string(d.ID))
		}
	}
	return res, nil
}

// ReleaseDuts implements service interfaces.
func (q *DroneQueenImpl) ReleaseDuts(ctx context.Context, req *api.ReleaseDutsRequest) (res *api.ReleaseDutsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	drone := entities.DroneID(req.GetDroneUuid())
	if drone == "" {
		return nil, errors.Reason("drone UUID must be supplied").Err()
	}
	for _, dut := range req.GetDuts() {
		dutID := entities.DUTID(dut)
		f := func(ctx context.Context) error {
			dut := entities.DUT{
				ID:    dutID,
				Group: entities.DUTGroupKey(ctx),
			}
			if err := datastore.Get(ctx, &dut); err != nil {
				if datastore.IsErrNoSuchEntity(err) {
					return nil
				}
				return errors.Annotate(err, "get DUT %s", dutID).Err()
			}
			if dut.AssignedDrone != drone {
				return nil
			}
			dut.AssignedDrone = ""
			if err := datastore.Put(ctx, &dut); err != nil {
				return errors.Annotate(err, "modify DUT %s", dutID).Err()
			}
			return nil
		}
		if err := datastore.RunInTransaction(ctx, f, nil); err != nil {
			return nil, err
		}
	}
	return &api.ReleaseDutsResponse{}, nil
}

// DeclareDuts implements service interfaces.
func (q *DroneQueenImpl) DeclareDuts(ctx context.Context, req *api.DeclareDutsRequest) (res *api.DeclareDutsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	f := func(ctx context.Context) error {
		// Get existing DUTs.
		q := datastore.NewQuery(entities.DUTKind).Ancestor(entities.DUTGroupKey(ctx))
		var duts []entities.DUT
		if err := datastore.GetAll(ctx, q, &duts); err != nil {
			return errors.Annotate(err, "get existing DUTs").Err()
		}
		existing := make(map[entities.DUTID]*entities.DUT)
		for i := range duts {
			existing[duts[i].ID] = &duts[i]
		}
		// Track newly declared DUTs and undrain re-declared DUTs.
		var modifiedDUTs []*entities.DUT
		var newDUTs []entities.DUTID
		declared := make(map[entities.DUTID]bool)
		reqDUTs := filterInvalidDUTs(req.GetDuts())
		for _, dut := range reqDUTs {
			dutID := entities.DUTID(dut)
			if dut, ok := existing[dutID]; ok {
				dut.Draining = false
				modifiedDUTs = append(modifiedDUTs, dut)
			} else {
				newDUTs = append(newDUTs, dutID)
			}
			declared[dutID] = true
		}
		// Drain existing DUTs that were not declared.
		for i := range duts {
			if !declared[duts[i].ID] {
				duts[i].Draining = true
				modifiedDUTs = append(modifiedDUTs, &duts[i])
			}
		}
		// Update modified DUTs.
		if err := datastore.Put(ctx, modifiedDUTs); err != nil {
			return errors.Annotate(err, "modify DUTs").Err()
		}
		// Add newly declared DUTs.
		k := entities.DUTGroupKey(ctx)
		for _, dut := range newDUTs {
			if err := datastore.Put(ctx, &entities.DUT{ID: dut, Group: k}); err != nil {
				return errors.Annotate(err, "add DUT %s", dut).Err()
			}
		}
		return nil
	}
	if err := datastore.RunInTransaction(ctx, f, nil); err != nil {
		return nil, err
	}
	return &api.DeclareDutsResponse{}, nil
}

func filterInvalidDUTs(s []string) []string {
	valid := make([]string, 0, len(s))
	for _, s := range s {
		if s == "" {
			continue
		}
		valid = append(valid, s)
	}
	return valid
}

// ListDrones implements service interfaces.
func (q *DroneQueenImpl) ListDrones(ctx context.Context, req *api.ListDronesRequest) (res *api.ListDronesResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	var drones []entities.Drone
	if err := datastore.GetAll(ctx, datastore.NewQuery(entities.DroneKind), &drones); err != nil {
		return nil, errors.Annotate(err, "get all drones").Err()
	}
	res = &api.ListDronesResponse{}
	for _, d := range drones {
		// TODO(ayatane): Log this error?
		t, _ := ptypes.TimestampProto(d.Expiration)
		res.Drones = append(res.Drones, &api.ListDronesResponse_Drone{
			Id:             string(d.ID),
			ExpirationTime: t,
		})
	}
	return res, nil
}

// ListDuts implements service interfaces.
func (q *DroneQueenImpl) ListDuts(ctx context.Context, req *api.ListDutsRequest) (res *api.ListDutsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	var duts []entities.DUT
	if err := datastore.GetAll(ctx, datastore.NewQuery(entities.DUTKind), &duts); err != nil {
		return nil, errors.Annotate(err, "get all DUTs").Err()
	}
	res = &api.ListDutsResponse{}
	for _, d := range duts {
		res.Duts = append(res.Duts, &api.ListDutsResponse_Dut{
			Id:            string(d.ID),
			AssignedDrone: string(d.AssignedDrone),
			Draining:      d.Draining,
		})
	}
	return res, nil
}

func (q *DroneQueenImpl) now() time.Time {
	if q.nowFunc != nil {
		return q.nowFunc()
	}
	return time.Now()
}
