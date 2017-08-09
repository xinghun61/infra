package pubsubalerts

import (
	"sort"
	"testing"

	"golang.org/x/net/context"

	helper "infra/monitoring/analyzer/test"
	"infra/monitoring/messages"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"

	. "github.com/smartystreets/goconvey/convey"
)

func sortedKeys(s map[string]*messages.Build) []string {
	keys := []string{}
	for k := range s {
		keys = append(keys, k)
	}

	sort.Strings(keys)
	return keys
}

func newTestContext() context.Context {
	ctx := gaetesting.TestingContext()
	ta := datastore.GetTestable(ctx)
	ta.AddIndexes(&datastore.IndexDefinition{
		Kind: storedAlertKind,
		SortBy: []datastore.IndexColumn{
			{
				Property: "Status",
			},
			{
				Property: "FailingBuilders",
			},
		},
	})
	// TODO(seanmccullough): relax this so we can test distributed consistency failure modes.
	ta.Consistent(true)
	return ctx
}

type newStoreFunc func() AlertStore

func TestHandleBuildPersistent(t *testing.T) {
	testHandleBuild(func() AlertStore { return NewAlertStore() }, t)
}

func TestHandleBuildInMem(t *testing.T) {
	testHandleBuild(func() AlertStore { return NewInMemAlertStore() }, t)
}

func testHandleBuild(newStore newStoreFunc, t *testing.T) {
	Convey("should return an error on nil build", t, func() {
		ctx := newTestContext()
		store := newStore()
		b := &BuildHandler{Store: store}
		err := b.HandleBuild(ctx, nil)
		So(err, ShouldNotEqual, nil)
	})

	Convey("build with one newly failing step", t, func() {
		ctx := newTestContext()
		store := newStore()
		b := &BuildHandler{Store: store}

		bf := helper.NewBuilderFaker("fake.master", "fake.builder").
			Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
			Step("fake step").Results(0).BuilderFaker.
			Build(1).Times(2, 3).IncludeChanges("http://repo", "refs/heads/master@{#291570}").
			Step("fake other step").Results(2).BuilderFaker

		for _, buildKey := range sortedKeys(bf.Builds) {
			err := b.HandleBuild(ctx, bf.Builds[buildKey])

			So(err, ShouldEqual, nil)
		}

		alerts, _ := store.ActiveAlertsForBuilder(ctx, "fake.master", "fake.builder")

		So(len(alerts), ShouldEqual, 1)
		So(len(alerts[0].FailingBuilders), ShouldEqual, 1)

		expectedAlerts := []*StoredAlert{
			{
				Master:          "fake.master",
				ID:              1,
				Status:          StatusActive,
				Signature:       "fake other step",
				FailingBuilders: stringSet{"fake.builder": struct{}{}},
				FailingBuilds:   []StoredBuild{{"fake.master", "fake.builder", 1}},
				PassingBuilders: stringSet{},
			},
		}

		So(alerts, ShouldResemble, expectedAlerts)
	})

	Convey("build with one newly passing step", t, func() {
		ctx := newTestContext()
		store := newStore()
		b := &BuildHandler{Store: store}
		bf := helper.NewBuilderFaker("fake.master", "fake.builder").
			Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
			Step("fake step").Results(2).BuilderFaker.
			Build(1).Times(2, 3).IncludeChanges("http://repo", "refs/heads/master@{#291570}").
			Step("fake step").Results(0).BuilderFaker

		for _, buildKey := range sortedKeys(bf.Builds) {
			err := b.HandleBuild(ctx, bf.Builds[buildKey])
			So(err, ShouldEqual, nil)
		}

		alerts, _ := store.ActiveAlertsForBuilder(ctx, "fake.master", "fake.builder")
		So(len(alerts), ShouldEqual, 0)
	})

	Convey("build with two failing steps", t, func() {
		ctx := newTestContext()
		store := newStore()
		b := &BuildHandler{Store: store}
		bf := helper.NewBuilderFaker("fake.master", "fake.builder").
			Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
			Step("fake_step").Results(2).BuildFaker.
			Step("other step").Results(2).BuilderFaker

		failingBuilds := []StoredBuild{}

		for _, buildKey := range sortedKeys(bf.Builds) {
			build := bf.Builds[buildKey]
			err := b.HandleBuild(ctx, build)
			So(err, ShouldEqual, nil)
			failingBuilds = append(failingBuilds, storedBuild(build))
		}

		alerts, _ := store.ActiveAlertsForBuilder(ctx, "fake.master", "fake.builder")
		So(len(alerts), ShouldEqual, 2)

		expectedAlerts := []*StoredAlert{
			{
				ID:              1,
				Master:          "fake.master",
				Status:          StatusActive,
				Signature:       "fake_step",
				FailingBuilders: stringSet{"fake.builder": struct{}{}},
				FailingBuilds:   failingBuilds,
				PassingBuilders: stringSet{},
			},
			{
				ID:              2,
				Master:          "fake.master",
				Status:          StatusActive,
				Signature:       "other step",
				FailingBuilders: stringSet{"fake.builder": struct{}{}},
				FailingBuilds:   failingBuilds,
				PassingBuilders: stringSet{},
			},
		}

		So(alerts, ShouldResemble, expectedAlerts)
	})

	Convey("build with two failing steps, followed by a build with one failing step", t, func() {
		ctx := newTestContext()
		store := newStore()
		b := &BuildHandler{Store: store}
		bf := helper.NewBuilderFaker("fake.master", "fake.builder").
			Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
			Step("fake_step").Results(2).BuildFaker.
			Step("other step").Results(2).BuilderFaker.
			Build(1).Times(2, 3).IncludeChanges("http://repo", "refs/heads/master@{#291570}").
			Step("fake_step").Results(0).BuildFaker.
			Step("other step").Results(2).BuilderFaker

		failingBuilds := []StoredBuild{}
		for _, buildKey := range sortedKeys(bf.Builds) {
			build := bf.Builds[buildKey]
			err := b.HandleBuild(ctx, build)
			So(err, ShouldEqual, nil)
			failingBuilds = append(failingBuilds, storedBuild(build))
		}

		alerts, _ := store.ActiveAlertsForBuilder(ctx, "fake.master", "fake.builder")
		So(len(alerts), ShouldEqual, 1)

		expectedAlerts := []*StoredAlert{
			{
				Master:          "fake.master",
				ID:              2,
				Status:          StatusActive,
				Signature:       "other step",
				FailingBuilders: stringSet{"fake.builder": struct{}{}},
				FailingBuilds:   failingBuilds,
				PassingBuilders: stringSet{},
			},
		}

		So(alerts, ShouldResemble, expectedAlerts)
	})

	Convey("build with two failing steps, followed by a build with one failing step, delivered out of order", t, func() {
		ctx := newTestContext()
		store := newStore()
		b := &BuildHandler{Store: store}
		bf := helper.NewBuilderFaker("fake.master", "fake.builder").
			Build(1).Times(2, 3).IncludeChanges("http://repo", "refs/heads/master@{#291570}").
			Step("fake_step").Results(0).BuildFaker.
			Step("other step").Results(2).BuilderFaker.
			Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
			Step("fake_step").Results(2).BuildFaker.
			Step("other step").Results(2).BuilderFaker

		failingBuilds := []StoredBuild{}
		for _, buildKey := range sortedKeys(bf.Builds) {
			build := bf.Builds[buildKey]
			err := b.HandleBuild(ctx, build)
			So(err, ShouldEqual, nil)
			failingBuilds = append(failingBuilds, storedBuild(build))
		}

		alerts, _ := store.ActiveAlertsForBuilder(ctx, "fake.master", "fake.builder")
		So(len(alerts), ShouldEqual, 1)

		expectedAlerts := []*StoredAlert{
			{
				Master:          "fake.master",
				ID:              2,
				Status:          StatusActive,
				Signature:       "other step",
				FailingBuilders: stringSet{"fake.builder": struct{}{}},
				FailingBuilds:   failingBuilds,
				PassingBuilders: stringSet{},
			},
		}

		So(alerts, ShouldResemble, expectedAlerts)
	})

	Convey("build with one failing step, followed by a build with two failing steps, delivered out of order", t, func() {
		ctx := newTestContext()
		store := newStore()
		b := &BuildHandler{Store: store}
		bf := helper.NewBuilderFaker("fake.master", "fake.builder").
			Build(1).Times(2, 3).IncludeChanges("http://repo", "refs/heads/master@{#291570}").
			Step("fake_step").Results(2).BuildFaker.
			Step("other step").Results(2).BuilderFaker.
			Build(0).Times(0, 1).IncludeChanges("http://repo", "refs/heads/master@{#291569}").
			Step("fake_step").Results(0).BuildFaker.
			Step("other step").Results(2).BuilderFaker

		failingBuilds := []StoredBuild{}
		for _, buildKey := range sortedKeys(bf.Builds) {
			build := bf.Builds[buildKey]
			err := b.HandleBuild(ctx, build)
			So(err, ShouldEqual, nil)
			failingBuilds = append(failingBuilds, storedBuild(build))
		}

		alerts, _ := store.ActiveAlertsForBuilder(ctx, "fake.master", "fake.builder")
		So(len(alerts), ShouldEqual, 2)

		expectedAlerts := []*StoredAlert{
			{
				Master:          "fake.master",
				ID:              1,
				Status:          StatusActive,
				Signature:       "other step",
				FailingBuilders: stringSet{"fake.builder": struct{}{}},
				FailingBuilds:   failingBuilds,
				PassingBuilders: stringSet{},
			},
			{
				Master:          "fake.master",
				ID:              2,
				Status:          StatusActive,
				Signature:       "fake_step",
				FailingBuilders: stringSet{"fake.builder": struct{}{}},
				FailingBuilds:   failingBuilds[1:],
				PassingBuilders: stringSet{},
			},
		}

		So(alerts, ShouldResemble, expectedAlerts)
	})
}
