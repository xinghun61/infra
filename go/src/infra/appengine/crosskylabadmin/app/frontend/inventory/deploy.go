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

package inventory

import (
	"fmt"
	"strings"

	"sort"
	"strconv"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/datastore/deploy"
	"infra/appengine/crosskylabadmin/app/frontend/internal/gitstore"
	"infra/appengine/crosskylabadmin/app/frontend/internal/swarming"
	"infra/appengine/crosskylabadmin/app/frontend/internal/worker"
	"infra/libs/skylab/inventory"

	"github.com/golang/protobuf/proto"
	"github.com/google/uuid"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// DeployDut implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) DeployDut(ctx context.Context, req *fleet.DeployDutRequest) (resp *fleet.DeployDutResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err = req.Validate(); err != nil {
		return nil, err
	}

	allSpecs, err := parseManyDUTSpecs(req.GetNewSpecs())
	if err != nil {
		return nil, err
	}
	for _, specs := range allSpecs {
		if specs.GetHostname() == "" {
			return nil, status.Error(codes.InvalidArgument, "DUT hostname not set in new_specs")
		}
	}

	s, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}
	sc, err := is.newSwarmingClient(ctx, config.Get(ctx).Swarming.Host)
	if err != nil {
		return nil, err
	}

	attemptID, err := initializeDeployAttempt(ctx)
	if err != nil {
		return nil, err
	}

	actions := req.GetActions()
	options := req.GetOptions()

	for _, specs := range allSpecs {
		ds := deployDUT(ctx, s, sc, attemptID, specs, actions, options)
		updateDeployStatusIgnoringErrors(ctx, attemptID, ds)
	}
	return &fleet.DeployDutResponse{DeploymentId: attemptID}, nil
}

// RedeployDut implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) RedeployDut(ctx context.Context, req *fleet.RedeployDutRequest) (resp *fleet.RedeployDutResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err = req.Validate(); err != nil {
		return nil, err
	}

	oldSpecs, err := parseDUTSpecs(req.GetOldSpecs())
	if err != nil {
		return nil, err
	}
	newSpecs, err := parseDUTSpecs(req.GetNewSpecs())
	if err != nil {
		return nil, err
	}
	if oldSpecs.GetId() == "" {
		return nil, status.Errorf(codes.InvalidArgument, "empty ID in old_specs")
	}
	if newSpecs.GetId() != oldSpecs.GetId() {
		return nil, status.Errorf(codes.InvalidArgument, "new_specs ID %s does not match old_specs ID %s",
			newSpecs.GetId(), oldSpecs.GetId())
	}

	s, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}
	sc, err := is.newSwarmingClient(ctx, config.Get(ctx).Swarming.Host)
	if err != nil {
		return nil, err
	}

	attemptID, err := initializeDeployAttempt(ctx)
	if err != nil {
		return nil, err
	}
	ds := redeployDUT(ctx, s, sc, attemptID, oldSpecs, newSpecs, req.GetActions(), req.GetOptions())
	updateDeployStatusIgnoringErrors(ctx, attemptID, ds)
	return &fleet.RedeployDutResponse{DeploymentId: attemptID}, nil
}

// GetDeploymentStatus implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) GetDeploymentStatus(ctx context.Context, req *fleet.GetDeploymentStatusRequest) (resp *fleet.GetDeploymentStatusResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err = req.Validate(); err != nil {
		return nil, err
	}

	sc, err := is.newSwarmingClient(ctx, config.Get(ctx).Swarming.Host)
	if err != nil {
		return nil, err
	}

	ds, err := deploy.GetStatus(ctx, req.DeploymentId)
	if err != nil {
		return nil, status.Errorf(codes.NotFound, "no deployment attempt with ID %s", req.DeploymentId)
	}
	if !ds.IsFinal {
		if err = refreshDeployStatus(ctx, sc, ds); err != nil {
			return nil, err
		}
		if err := deploy.UpdateStatus(ctx, req.DeploymentId, ds); err != nil {
			return nil, err
		}
	}

	resp = &fleet.GetDeploymentStatusResponse{
		Status:    ds.Status,
		ChangeUrl: ds.ChangeURL,
		Message:   ds.Reason,
	}
	if ds.TaskID != "" {
		resp.TaskUrl = swarming.URLForTask(ctx, ds.TaskID)
	}
	return resp, nil
}

// DeleteDuts implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) DeleteDuts(ctx context.Context, req *fleet.DeleteDutsRequest) (resp *fleet.DeleteDutsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err = req.Validate(); err != nil {
		return nil, err
	}
	s, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}
	var changeURL string
	var removedIDs []string
	f := func() error {
		if err2 := s.Refresh(ctx); err2 != nil {
			return err2
		}
		removedDUTs := removeDUTWithHostnames(s, req.Hostnames)
		url, err2 := s.Commit(ctx, fmt.Sprintf("delete %d duts", len(removedDUTs)))
		if gitstore.IsEmptyErr(err2) {
			return nil
		}
		if err2 != nil {
			return err2
		}

		// Captured variables only on success, hence at most once.
		changeURL = url
		removedIDs = make([]string, 0, len(removedDUTs))
		for _, d := range removedDUTs {
			removedIDs = append(removedIDs, d.GetCommon().GetId())
		}
		return nil
	}
	if err = retry.Retry(ctx, transientErrorRetries(), f, retry.LogCallback(ctx, "DeleteDut")); err != nil {
		return nil, err
	}

	return &fleet.DeleteDutsResponse{
		ChangeUrl: changeURL,
		Ids:       removedIDs,
	}, nil

}

// initializeDeployAttempt initializes internal state for a deployment attempt.
//
// This function returns a new ID for this deployment attempt.
func initializeDeployAttempt(ctx context.Context) (string, error) {
	attemptID, err := deploy.PutStatus(ctx, &deploy.Status{
		Status: fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_FAILED,
		Reason: "unknown",
	})
	if err != nil {
		return "", errors.Annotate(err, "initialize deploy attempt").Err()
	}
	return attemptID, nil
}

// deployDUT kicks off a new DUT deployment.
//
// Errors are communicated via returned deploy.Status
func deployDUT(ctx context.Context, s *gitstore.InventoryStore, sc clients.SwarmingClient, attemptID string, nd *inventory.CommonDeviceSpecs, a *fleet.DutDeploymentActions, o *fleet.DutDeploymentOptions) *deploy.Status {
	var err error
	ds := &deploy.Status{Status: fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_IN_PROGRESS}
	ds.ChangeURL, err = addDUTToFleet(ctx, s, nd, o.GetAssignServoPortIfMissing())
	if err != nil {
		failDeployStatus(ctx, ds, fmt.Sprintf("failed to add dut to fleet: %s", err))
		return ds
	}
	ds.TaskID, err = scheduleDUTPreparationTask(ctx, sc, nd.GetId(), a)
	if err != nil {
		failDeployStatus(ctx, ds, fmt.Sprintf("failed to create deploy task: %s", err))
		return ds
	}
	return ds
}

// addDUTToFleet adds a new DUT with given specs to the inventory and assigns
// it to a drone.
//
// This function returns the URL for the inventory update change.
// This function updates nd.Id to a ID unique in the inventory.
// TODO(pprabhu) Updating an arbitrary function argument is yucky. FixMe.
func addDUTToFleet(ctx context.Context, s *gitstore.InventoryStore, nd *inventory.CommonDeviceSpecs, pickServoPort bool) (string, error) {
	var respURL string
	f := func() error {
		// Clone device specs before modifications so that changes don't leak
		// across retries.
		d := proto.Clone(nd).(*inventory.CommonDeviceSpecs)

		if err := s.Refresh(ctx); err != nil {
			return errors.Annotate(err, "add dut to fleet").Err()
		}

		c := newGlobalInvCache(ctx, s)
		hostname := d.GetHostname()
		if _, ok := c.hostnameToID[hostname]; ok {
			return errors.Reason("dut with hostname %s already exists", hostname).Err()

		}

		if pickServoPort && !hasServoPortAttribute(d) {
			if err := assignNewServoPort(s.Lab.Duts, d); err != nil {
				return errors.Annotate(err, "add dut to fleet").Err()
			}
		}

		id := addDUTToStore(s, d)
		// TODO(ayatane): Implement this better than just regenerating the cache.
		c = newGlobalInvCache(ctx, s)
		if _, err := assignDUT(ctx, c, id); err != nil {
			return errors.Annotate(err, "add dut to fleet").Err()
		}

		url, err := s.Commit(ctx, fmt.Sprintf("Add new DUT %s", hostname))
		if err != nil {
			return errors.Annotate(err, "add dut to fleet").Err()
		}

		respURL = url
		nd.Id = &id
		return nil
	}

	err := retry.Retry(ctx, transientErrorRetries(), f, retry.LogCallback(ctx, "addDUTToFleet"))
	return respURL, err
}

const (
	servoHostAttributeKey = "servo_host"
	servoPortAttributeKey = "servo_port"
)

// assignNewServoPort adds a valid servo port attribute to d
//
// This function returns an error if d does not have the servo host attribute.
// The assigned servo port value is unique among all the duts with the same
// servo host attribute.
func assignNewServoPort(duts []*inventory.DeviceUnderTest, d *inventory.CommonDeviceSpecs) error {
	servoHost, found := getAttributeByKey(d, servoHostAttributeKey)
	if !found {
		return errors.Reason("no servo_host attribute in specs").Err()
	}

	used := usedServoPorts(duts, servoHost)
	p, err := findFreePort(used)
	if err != nil {
		return err
	}
	k := servoPortAttributeKey
	v := strconv.Itoa(p)
	d.Attributes = append(d.Attributes, &inventory.KeyValue{Key: &k, Value: &v})
	return nil
}

// usedServoPorts finds the servo ports used by duts with the given servo host
// attribute.
func usedServoPorts(duts []*inventory.DeviceUnderTest, servoHost string) []int {
	used := []int{}
	for _, d := range duts {
		c := d.GetCommon()
		if sh, found := getAttributeByKey(c, servoHostAttributeKey); found && sh == servoHost {
			if p, found := getAttributeByKey(c, servoPortAttributeKey); found {
				ip, err := strconv.ParseInt(p, 10, 32)
				if err != nil {
					// This is not the right place to enforce servo_port correctness for other DUTs.
					// All we care about is that the port we pick will not conflict with
					// this corrupted entry.
					continue
				}
				used = append(used, int(ip))
			}
		}
	}
	return used
}

// findFreePort finds a valid port that is not in use.
//
// This function returns an error if no free port is found.
// This function modifies the slice of ports provided.
func findFreePort(used []int) (int, error) {
	sort.Sort(sort.Reverse(sort.IntSlice(used)))
	// This range is consistent with the range of ports generated by servod:
	// https://chromium.googlesource.com/chromiumos/third_party/hdctools/+/cf5f8027b9d3015db75df4853e37ea7a2f1ac538/servo/servod.py#36
	for p := 9999; p > 9900; p-- {
		if len(used) == 0 || p != used[0] {
			return p, nil
		}
		used = used[1:]
	}
	return -1, errors.Reason("no free valid ports").Err()
}

// addDUTToStore adds a new DUT with the given specs to the store.
//
// This function returns a new ID for the added DUT.
func addDUTToStore(s *gitstore.InventoryStore, nd *inventory.CommonDeviceSpecs) string {
	id := uuid.New().String()
	nd.Id = &id
	// TODO(crbug/912977) DUTs under deployment are not marked specially in the
	// inventory yet. This causes two problems:
	// - Another admin task (say repair) may get scheduled on the new bot
	//   before the deploy task we create.
	// - If the deploy task fails, the DUT will still enter the fleet, but may
	//   not be ready for use.
	s.Lab.Duts = append(s.Lab.Duts, &inventory.DeviceUnderTest{
		Common: nd,
	})
	return id
}

// scheduleDUTPreparationTask schedules a Skylab DUT preparation task.
func scheduleDUTPreparationTask(ctx context.Context, sc clients.SwarmingClient, dutID string, a *fleet.DutDeploymentActions) (string, error) {
	taskCfg := config.Get(ctx).GetEndpoint().GetDeployDut()
	tags := swarming.AddCommonTags(ctx, fmt.Sprintf("deploy_task:%s", dutID))
	at := worker.DeployTaskWithActions(ctx, deployActionArgs(a))
	tags = append(tags, at.Tags...)
	return sc.CreateTask(ctx, at.Name, swarming.SetCommonTaskArgs(ctx, &clients.SwarmingCreateTaskArgs{
		Cmd:                  at.Cmd,
		DutID:                dutID,
		ExecutionTimeoutSecs: taskCfg.GetTaskExecutionTimeout().GetSeconds(),
		ExpirationSecs:       taskCfg.GetTaskExpirationTimeout().GetSeconds(),
		Priority:             taskCfg.GetTaskPriority(),
		Tags:                 tags,
	}))
}

// redeployDUT kicks off a redeployment of an existing DUT.
//
// Errors are communicated via returned deploy.Status
func redeployDUT(ctx context.Context, s *gitstore.InventoryStore, sc clients.SwarmingClient, attemptID string, oldSpecs, newSpecs *inventory.CommonDeviceSpecs, a *fleet.DutDeploymentActions, o *fleet.DutDeploymentOptions) *deploy.Status {
	var err error
	ds := &deploy.Status{Status: fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_IN_PROGRESS}

	if !proto.Equal(oldSpecs, newSpecs) {
		ds.ChangeURL, err = updateDUTSpecs(ctx, s, oldSpecs, newSpecs, o.GetAssignServoPortIfMissing())
		if err != nil {
			failDeployStatus(ctx, ds, fmt.Sprintf("failed to update DUT specs: %s", err))
			return ds
		}
	}

	ds.TaskID, err = scheduleDUTPreparationTask(ctx, sc, oldSpecs.GetId(), a)
	if err != nil {
		failDeployStatus(ctx, ds, fmt.Sprintf("failed to create deploy task: %s", err))
		return ds
	}
	return ds
}

// updateDUTSpecs updates the DUT specs for an existing DUT in the inventory.
func updateDUTSpecs(ctx context.Context, s *gitstore.InventoryStore, od, nd *inventory.CommonDeviceSpecs, pickServoPort bool) (string, error) {
	var respURL string
	f := func() error {
		// Clone device specs before modifications so that changes don't leak
		// across retries.
		d := proto.Clone(nd).(*inventory.CommonDeviceSpecs)

		if err := s.Refresh(ctx); err != nil {
			return errors.Annotate(err, "add new dut to inventory").Err()
		}

		if pickServoPort && !hasServoPortAttribute(d) {
			if err := assignNewServoPort(s.Lab.Duts, d); err != nil {
				return errors.Annotate(err, "add dut to fleet").Err()
			}
		}

		dut, exists := getDUTByID(s.Lab, od.GetId())
		if !exists {
			return status.Errorf(codes.NotFound, "no DUT with ID %s", od.GetId())
		}
		// TODO(crbug/929776) DUTs under deployment are not marked specially in the
		// inventory yet. This causes two problems:
		// - Another admin task (say repair) may get scheduled on the new bot
		//   before the deploy task we create.
		// - If the deploy task fails, the DUT will still enter the fleet, but may
		//   not be ready for use.
		if !proto.Equal(dut.GetCommon(), od) {
			return errors.Reason("DUT specs update conflict").Err()
		}
		dut.Common = d

		url, err := s.Commit(ctx, fmt.Sprintf("Update DUT %s", od.GetId()))
		if err != nil {
			return errors.Annotate(err, "update DUT specs").Err()
		}

		respURL = url
		return nil
	}
	err := retry.Retry(ctx, transientErrorRetries(), f, retry.LogCallback(ctx, "updateDUTSpecs"))
	return respURL, err
}

// refreshDeployStatus refreshes the status of given deployment attempt from
// Swarming.
func refreshDeployStatus(ctx context.Context, sc clients.SwarmingClient, ds *deploy.Status) error {
	if ds.TaskID == "" {
		failDeployStatus(ctx, ds, "missing deploy task ID in deploy request entry")
		return nil
	}

	tr, err := sc.GetTaskResult(ctx, ds.TaskID)
	if err != nil {
		return errors.Annotate(err, "refresh deploy status").Err()
	}

	switch tr.State {
	case "COMPLETED":
		if tr.Failure || tr.InternalFailure {
			ds.Status = fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_FAILED
		} else {
			ds.Status = fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_SUCCEEDED
		}
		ds.IsFinal = true
	case "PENDING", "RUNNING":
		ds.Status = fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_IN_PROGRESS
	default:
		failDeployStatus(ctx, ds, fmt.Sprintf("unhandled deploy task state: %s", tr.State))
	}
	return nil
}

// failDeployStatus updates ds to correspond to a failed deploy with the given
// reason.
func failDeployStatus(ctx context.Context, ds *deploy.Status, reason string) {
	ds.IsFinal = true
	ds.Status = fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_FAILED
	ds.Reason = reason
	logging.Errorf(ctx, "Failed deploy: %#v", ds)
}

func updateDeployStatusIgnoringErrors(ctx context.Context, attemptID string, ds *deploy.Status) {
	if err := deploy.UpdateStatus(ctx, attemptID, ds); err != nil {
		logging.Errorf(ctx, "Failed to update status for deploy attempt %s to %v", attemptID, ds)
	}
}

// removeDUTWithHostnames deletes duts with the given hostnames.
//
// The function returns the deleted duts.
// If multiple DUTs have the same hostname, that is in hostnames, they are all deleted.
func removeDUTWithHostnames(s *gitstore.InventoryStore, hostnames []string) []*inventory.DeviceUnderTest {
	duts := s.Lab.Duts
	toRemove := stringset.NewFromSlice(hostnames...)
	removedDuts := make([]*inventory.DeviceUnderTest, 0, len(hostnames))
	for i := 0; i < len(duts); {
		d := duts[i]
		h := d.GetCommon().GetHostname()
		if !toRemove.Has(h) {
			i++
			continue
		}
		removedDuts = append(removedDuts, d)
		duts = deleteAtIndex(duts, i)
	}
	s.Lab.Duts = duts
	return removedDuts
}

func deleteAtIndex(duts []*inventory.DeviceUnderTest, i int) []*inventory.DeviceUnderTest {
	copy(duts[i:], duts[i+1:])
	duts[len(duts)-1] = nil
	return duts[:len(duts)-1]
}

func parseDUTSpecs(specs []byte) (*inventory.CommonDeviceSpecs, error) {
	var parsed inventory.CommonDeviceSpecs
	if err := proto.Unmarshal(specs, &parsed); err != nil {
		return nil, errors.Annotate(err, "parse DUT specs").Tag(grpcutil.InvalidArgumentTag).Err()
	}
	return &parsed, nil
}

func parseManyDUTSpecs(specsArr [][]byte) ([]*inventory.CommonDeviceSpecs, error) {
	var out []*inventory.CommonDeviceSpecs
	out = make([]*inventory.CommonDeviceSpecs, 0, len(specsArr))
	for _, item := range specsArr {
		if parsed, err := parseDUTSpecs(item); err == nil {
			out = append(out, parsed)
		} else {
			return nil, err
		}
	}
	return out, nil
}

func hasServoPortAttribute(d *inventory.CommonDeviceSpecs) bool {
	_, found := getAttributeByKey(d, servoPortAttributeKey)
	return found
}

// getAttributeByKey by returns the value for the attribute with the given key,
// and whether the key was found.
func getAttributeByKey(d *inventory.CommonDeviceSpecs, key string) (string, bool) {
	for _, a := range d.Attributes {
		if *a.Key == key {
			return *a.Value, true
		}
	}
	return "", false
}

func deployActionArgs(a *fleet.DutDeploymentActions) string {
	s := make([]string, 0, 3)
	if a.GetStageImageToUsb() {
		s = append(s, "stage-usb")
	}
	if a.GetInstallFirmware() {
		s = append(s, "install-firmware")
	}
	if a.GetInstallTestImage() {
		s = append(s, "install-test-image")
	}
	return strings.Join(s, ",")
}
