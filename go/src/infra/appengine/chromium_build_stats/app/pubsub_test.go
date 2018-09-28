package app

import (
	"bytes"
	"compress/gzip"
	"fmt"
	"reflect"
	"testing"
	"time"

	"google.golang.org/api/option"

	"cloud.google.com/go/storage"
	"github.com/GoogleCloudPlatform/google-cloud-go-testing/storage/stiface"
	"golang.org/x/net/context"

	"infra/appengine/chromium_build_stats/ninjalog"
)

var (
	stepsTestCase = []ninjalog.Step{
		{
			Start:   76 * time.Millisecond,
			End:     187 * time.Millisecond,
			Out:     "resources/inspector/devtools_extension_api.js",
			CmdHash: "75430546595be7c2",
		},
		{
			Start:   80 * time.Millisecond,
			End:     284 * time.Millisecond,
			Out:     "gen/autofill_regex_constants.cc",
			CmdHash: "fa33c8d7ce1d8791",
		},
		{
			Start:   78 * time.Millisecond,
			End:     286 * time.Millisecond,
			Out:     "gen/angle/commit_id.py",
			CmdHash: "4ede38e2c1617d8c",
		},
		{
			Start:   79 * time.Millisecond,
			End:     287 * time.Millisecond,
			Out:     "gen/angle/copy_compiler_dll.bat",
			CmdHash: "9fb635ad5d2c1109",
		},
		{
			Start:   141 * time.Millisecond,
			End:     287 * time.Millisecond,
			Out:     "PepperFlash/manifest.json",
			CmdHash: "324f0a0b77c37ef",
		},
		{
			Start:   142 * time.Millisecond,
			End:     288 * time.Millisecond,
			Out:     "PepperFlash/libpepflashplayer.so",
			CmdHash: "1e2c2b7845a4d4fe",
		},
		{
			Start:   287 * time.Millisecond,
			End:     290 * time.Millisecond,
			Out:     "obj/third_party/angle/src/copy_scripts.actions_rules_copies.stamp",
			CmdHash: "b211d373de72f455",
		},
	}

	metadataTestCase = ninjalog.Metadata{
		BuildID:  12345,
		Platform: "linux",
		Argv:     []string{"../../../scripts/slave/compile.py", "--target", "Release", "--clobber", "--compiler=goma", "--", "all"},
		Cwd:      "/b/build/slave/Linux_x64/build/src",
		Compiler: "goma",
		Cmdline:  []string{"ninja", "-C", "/b/build/slave/Linux_x64/build/src/out/Release", "all", "-j50"},
		Exit:     0,
		StepName: "compile",
		Env: map[string]string{
			"LANG":    "en_US.UTF-8",
			"SHELL":   "/bin/bash",
			"HOME":    "/home/chrome-bot",
			"PWD":     "/b/build/slave/Linux_x64/build",
			"LOGNAME": "chrome-bot",
			"USER":    "chrome-bot",
			"PATH":    "/home/chrome-bot/slavebin:/b/depot_tools:/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin",
		},
		CompilerProxyInfo: "/tmp/compiler_proxy.build48-m1.chrome-bot.log.INFO.20140907-203827.14676",
		Jobs:              50,
		Raw:               `{"build_id": 12345, "platform": "linux", "argv": ["../../../scripts/slave/compile.py", "--target", "Release", "--clobber", "--compiler=goma", "--", "all"], "cmdline": ["ninja", "-C", "/b/build/slave/Linux_x64/build/src/out/Release", "all", "-j50"], "exit": 0, "step_name": "compile", "env": {"LANG": "en_US.UTF-8", "SHELL": "/bin/bash", "HOME": "/home/chrome-bot", "PWD": "/b/build/slave/Linux_x64/build", "LOGNAME": "chrome-bot", "USER": "chrome-bot", "PATH": "/home/chrome-bot/slavebin:/b/depot_tools:/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin" }, "compiler_proxy_info": "/tmp/compiler_proxy.build48-m1.chrome-bot.log.INFO.20140907-203827.14676", "cwd": "/b/build/slave/Linux_x64/build/src", "compiler": "goma"}`,
	}
)

type (
	client       struct{ stiface.Client }
	bucketHandle struct{ stiface.BucketHandle }
	objectHandle struct{ stiface.ObjectHandle }
	reader       struct {
		stiface.Reader
		buf bytes.Buffer
	}
)

func (client) Bucket(name string) stiface.BucketHandle {
	return bucketHandle{}
}

func (bucketHandle) Object(name string) stiface.ObjectHandle {
	return objectHandle{}
}

func (objectHandle) ReadCompressed(compressed bool) stiface.ObjectHandle {
	return objectHandle{}
}

func (objectHandle) NewReader(ctx context.Context) (stiface.Reader, error) {
	var r reader
	zw := gzip.NewWriter(&r.buf)
	_, err := zw.Write([]byte(`# ninja log v5
1020807	1020916	0	chrome.1	e101fd46be020cfc
84	9489	0	gen/libraries.cc	9001f3182fa8210e
1024369	1041522	0	chrome	aee9d497d56c9637
76	187	0	resources/inspector/devtools_extension_api.js	75430546595be7c2
80	284	0	gen/autofill_regex_constants.cc	fa33c8d7ce1d8791
78	286	0	gen/angle/commit_id.py	4ede38e2c1617d8c
79	287	0	gen/angle/copy_compiler_dll.bat	9fb635ad5d2c1109
141	287	0	PepperFlash/manifest.json	324f0a0b77c37ef
142	288	0	PepperFlash/libpepflashplayer.so	1e2c2b7845a4d4fe
287	290	0	obj/third_party/angle/src/copy_scripts.actions_rules_copies.stamp	b211d373de72f455
# end of ninja log
{"build_id": 12345, "platform": "linux", "argv": ["../../../scripts/slave/compile.py", "--target", "Release", "--clobber", "--compiler=goma", "--", "all"], "cmdline": ["ninja", "-C", "/b/build/slave/Linux_x64/build/src/out/Release", "all", "-j50"], "exit": 0, "step_name": "compile", "env": {"LANG": "en_US.UTF-8", "SHELL": "/bin/bash", "HOME": "/home/chrome-bot", "PWD": "/b/build/slave/Linux_x64/build", "LOGNAME": "chrome-bot", "USER": "chrome-bot", "PATH": "/home/chrome-bot/slavebin:/b/depot_tools:/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin" }, "compiler_proxy_info": "/tmp/compiler_proxy.build48-m1.chrome-bot.log.INFO.20140907-203827.14676", "cwd": "/b/build/slave/Linux_x64/build/src", "compiler": "goma"}
`))
	if err != nil {
		return nil, fmt.Errorf("failed to write gzip: %v", err)
	}
	if err := zw.Close(); err != nil {
		return nil, fmt.Errorf("failed to close gzip: %v", err)
	}
	return r, nil
}

func (reader) Close() error {
	return nil
}

func (r reader) Read(b []byte) (int, error) {
	return r.buf.Read(b)
}

func TestGetFile(t *testing.T) {
	ctx := context.Background()
	originalCreateClient := createClient
	defer func() {
		createClient = originalCreateClient
	}()
	createClient = func(ctx context.Context, opts ...option.ClientOption) (*storage.Client, error) {
		return &storage.Client{}, nil
	}

	originalCreateAdaptClient := createAdaptClient
	defer func() {
		createAdaptClient = originalCreateAdaptClient
	}()
	createAdaptClient = func(c *storage.Client) stiface.Client {
		return client{}
	}

	testName := "test"
	testID := "abc1234"
	got, err := getFile(ctx, testName, testID)
	want := &ninjalog.NinjaLog{
		Filename: "test",
		Start:    4,
		Steps:    stepsTestCase,
		Metadata: metadataTestCase,
	}
	if err != nil || !reflect.DeepEqual(got, want) {
		t.Errorf("getFile(ctx, %q, %q)=%v, %v; want %v, <nil>", testName, testID, got, err, want)
	}
}
