// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package compilerproxylog

import (
	"strings"
	"testing"
	"time"

	"github.com/google/go-cmp/cmp"
)

func BenchmarkParseTaskLine(b *testing.B) {
	for i := 0; i < b.N; i++ {
		parseTaskLine("I0911 17:44:06.493176  5786 compile_task.cc:923] Task:0 Start ../../third_party/webrtc/system_wrappers/source/condition_variable_posix.cc gomacc_pid=5838")
	}
}

func TestParse(t *testing.T) {
	logcontent := `Log file created at: 2014/09/11 17:43:51
Running on machine: chromeperf58
Log line format: [IWEF]mmdd hh:mm:ss.uuuuuu threadid file:line] msg
I0911 17:43:51.709230  5777 breakpad_linux.cc:51] initialized breakpad.
I0911 17:43:51.709625  5777 compiler_proxy.cc:1498] goma built revision 4a694601289a8f07a6d6439631049e1ad0914dfb@1409795845
I0911 17:43:51.709913  5777 compiler_proxy.cc:1508] goma flags:GOMA_API_KEY_FILE=/b/build/goma/goma.key
GOMA_COMPILER_PROXY_DAEMON_MODE=true
GOMA_COMPILER_PROXY_HTTP_THREADS=3 (auto configured)
GOMA_COMPILER_PROXY_THREADS=12 (auto configured)
GOMA_MAX_INCLUDE_CACHE_SIZE=0 (auto configured)
GOMA_MAX_POOLED_INCLUDE_DIR_CACHE=512 (auto configured)
GOMA_USE_SSL=true
I0911 17:43:51.723774  5777 auto_updater.cc:91] manifest /b/build/goma/x86_64/MANIFEST VERSION=68
I0911 17:43:51.723794  5777 compiler_proxy.cc:1513] goma version:68
I0911 17:43:51.723834  5777 compiler_proxy.cc:1351] setrlimit RLIMIT_NOFILE 4096 -> 4096
I0911 17:43:52.085327  5777 compiler_proxy.cc:1566] unix domain:/tmp/goma.ipc
I0911 17:43:52.085346  5777 compiler_proxy.cc:1586] max incoming: 1339 max_nfile=4096 FD_SETSIZE=1024 max_num_sockets=4096 USE_EPOLL=1 threads=12+3
I0911 17:44:01.012345  577  compile_service.cc:194] compiler_proxy_id_prefix:chrome-bot@chromeperf58:8088/2014-09-11T17:43:51.123456789+00:00/
I0911 17:44:06.493170  5786 compile_task.cc:923] Task:0 build_id:6235ce6e-d8e4-4e17-a9cf-e702a816834c
I0911 17:44:06.493176  5786 compile_task.cc:923] Task:0 Start ../../third_party/webrtc/system_wrappers/source/condition_variable_posix.cc gomacc_pid=5838
I0911 17:44:06.493830  5798 subprocess_task.cc:244] ../../third_party/llvm-build/Release+Asserts/bin/clang++ started pid=5844 state=RUN
I0911 17:44:06.493980  5787 compile_task.cc:923] Task:1 build_id:6235ce6e-d8e4-4e17-a9cf-e702a816834c
I0911 17:44:06.493988  5787 compile_task.cc:923] Task:1 Start ../../third_party/webrtc/common_audio/signal_processing/filter_ma_fast_q12.c gomacc_pid=5840
I0911 17:44:06.494810  5788 compile_task.cc:923] Task:2 build_id:6235ce6e-d8e4-4e17-a9cf-e702a816834c
I0911 17:44:06.494817  5788 compile_task.cc:923] Task:2 Start ../../third_party/lzma_sdk/7zBuf.c gomacc_pid=5842
I0911 17:44:06.495700 5790 compile_task.cc:923] Task:3 build_id:6235ce6e-d8e4-4e17-a9cf-e702a816834c
I0911 17:44:06.495704  5790 compile_task.cc:923] Task:3 Start ../../third_party/yasm/source/patched-yasm/tools/genmacro/genmacro.c gomacc_pid=5845
I0911 17:44:06.496720  5792 compile_task.cc:923] Task:4 build_id:6235ce6e-d8e4-4e17-a9cf-e702a816834c
I0911 17:44:06.496722  5792 compile_task.cc:923] Task:4 Start gen/ui/resources/grit/ui_resources_map.cc gomacc_pid=5848
I0911 17:44:06.497630 5794 compile_task.cc:923] Task:5 build_id:6235ce6e-d8e4-4e17-a9cf-e702a816834c
I0911 17:44:06.497638  5794 compile_task.cc:923] Task:5 Start linking ./dump_syms /search/search.cc gomacc_pid=5850
I0911 17:44:06.498120  5795 copmiler_service.cc:467] Task:6 build_id:6235ce6e-d8e4-4e17-a9cf-e702a816834c
I0911 17:44:06.498123  5795 copmiler_service.cc:467] Task:6 pending
I0911 17:44:06.498575  5796 compile_task.cc:923] Task:6 Start ../../components/search/search_switches.cc gomacc_pid=5852
I0911 17:44:07.410532  5798 subprocess_task.cc:255] ../../third_party/llvm-build/Release+Asserts/bin/clang++ terminated pid=5844 status=1
I0911 17:44:07.411144  5798 subprocess_task.cc:244] Task:0 started pid=5940 state=RUN
I0911 17:44:12.430022  5792 compile_task.cc:1610] Task:4 output need_rename for local_subproc -1
I0911 17:44:13.377951  5792 compile_task.cc:1813] Task:4 goma finished, killing subproc pid=-1
I0911 17:44:13.383539  5798 subprocess_task.cc:255] Task:0 terminated pid=5940 status=0
I0911 17:44:13.786922  5786 compile_task.cc:1992] Task:0 ReplyResponse: local finish, no goma
I0911 17:44:13.874645  5792 compile_task.cc:1992] Task:4 ReplyResponse: goma success
I0911 17:44:15.714953  5798 subprocess_task.cc:244] Task:5 started pid=6109 state=RUN
I0911 17:44:16.412282  5794 compile_task.cc:1610] Task:5 output need_rename for local_subproc 6109
I0911 17:44:16.524380  5798 subprocess_task.cc:255] Task:5 terminated pid=6109 status=0
I0911 17:44:16.524417  5798 subprocess_task.cc:244] Task:3 started pid=6124 state=RUN
I0911 17:44:16.601634  5794 compile_task.cc:1992] Task:5 ReplyResponse: should fallback
I0911 17:44:16.667843  5798 subprocess_task.cc:255] Task:3 terminated pid=6124 status=0
I0911 17:44:16.667868  5798 subprocess_task.cc:244] Task:2 started pid=6129 state=RUN
I0911 17:44:16.667989  5790 compile_task.cc:1992] Task:3 ReplyResponse: local finish, abort goma
I0911 17:44:16.700744  5798 subprocess_task.cc:255] Task:2 terminated pid=6129 status=0
I0911 17:44:16.700806  5798 subprocess_task.cc:244] Task:1 started pid=6134 state=RUN
I0911 17:44:16.700889  5788 compile_task.cc:1992] Task:2 ReplyResponse: local finish, abort goma
I0911 17:44:16.738137  5798 subprocess_task.cc:255] Task:1 terminated pid=6134 status=0
I0911 17:44:16.738234  5787 compile_task.cc:1992] Task:1 ReplyResponse: local finish, abort goma
I0911 17:44:16.835789  5798 subprocess_task.cc:244] Task:6 started pid=6144 state=RUN
I0911 17:44:16.879048  5798 subprocess_task.cc:255] Task:6 terminated pid=6144 status=0
I0911 17:44:16.879138  5796 compile_task.cc:1992] Task:6 ReplyResponse: local finish, abort goma
I0911 17:44:18.263380  5788 compile_task.cc:1741] Task:2 finished aborted in call exec state=CALL_EXEC abort=1
I0911 17:44:18.263375  5787 compile_task.cc:1741] Task:1 finished aborted in call exec state=CALL_EXEC abort=1
I0911 17:44:18.263375  5796 compile_task.cc:1741] Task:6 finished aborted in call exec state=CALL_EXEC abort=1
I0911 17:44:18.264058  5790 compile_task.cc:1741] Task:3 finished aborted in call exec state=CALL_EXEC abort=1
I0911 17:44:56.478301 14018 compiler_proxy.cc:1375] Dumping stats...
request: total=0 success=0 failure=0
I0911 17:44:56.478324 14018 worker_thread_manager.cc:339] thread[140693330720512]  tick=17 idle: 0 descriptors: poll_interval=500: PriLow[0 pendings  q=0 w=0] PriMed[0 pendings  q=0 w=6.9e-05] PriHigh[0 pendings  q=0 w=0] PriImmediate[0 pendings  q=0 w=0] : delayed=0: periodic=0
I0911 17:44:56.480223 14018 compiler_proxy.cc:1383] Dumping histogram...
ThreadpoolHttpServerRequestSize:  Basic stats: count: 4 min: 124 max: 232 mean: 178 stddev: 53
[ 64-128]: ##################################################2
[128-256]: ##################################################2

ThreadpoolHttpServerResponseSize:  Basic stats: count: 4 min: 21 max: 96 mean: 69 stddev: 28
[16- 32]: ################1
[32- 64]:
[64-128]: ##################################################3
I1124 14:32:56.480244 14018 compiler_proxy.cc:1391] Dumping serverz...
Frontend / Count
`
	cpl, err := Parse("compiler_proxy.INFO", strings.NewReader(logcontent))
	if err != nil {
		t.Fatalf(`Parse("compiler_proxy.INFO")=%v, %v; want=_, <nil>`, cpl, err)
	}
	if cpl.Filename != "compiler_proxy.INFO" {
		t.Errorf("cpl.Filename=%q; want=%q", cpl.Filename, "compiler_proxy.INFO")
	}
	if got, want := cpl.Created.Format("2006-01-02T15:04:05"), "2014-09-11T17:43:51"; got != want {
		t.Errorf("cpl.Created=%s (%v); want=%s", got, cpl.Created, want)
	}
	if got, want := cpl.Machine, "chromeperf58"; got != want {
		t.Errorf("cpl.Machine=%q; want=%q", got, want)
	}
	if got, want := cpl.GomaRevision, "4a694601289a8f07a6d6439631049e1ad0914dfb@1409795845"; got != want {
		t.Errorf("cpl.GomaRevision=%q; want=%q", got, want)
	}
	if got, want := cpl.GomaVersion, "68"; got != want {
		t.Errorf("cpl.GomaVersion=%q; want=%q", got, want)
	}
	if got, want := cpl.CompilerProxyIDPrefix, "chrome-bot@chromeperf58:8088/2014-09-11T17:43:51.123456789+00:00/"; got != want {
		t.Errorf("cpl.CompilerProxyIDPrefix=%q; want=%q", got, want)
	}
	if diff := cmp.Diff([]string{"6235ce6e-d8e4-4e17-a9cf-e702a816834c"}, cpl.BuildIDs); diff != "" {
		t.Errorf("cpl.BuildIDs: diff -want +got: %s", diff)
	}
	if got, want := cpl.GomaFlags, `GOMA_API_KEY_FILE=/b/build/goma/goma.key
GOMA_COMPILER_PROXY_DAEMON_MODE=true
GOMA_COMPILER_PROXY_HTTP_THREADS=3 (auto configured)
GOMA_COMPILER_PROXY_THREADS=12 (auto configured)
GOMA_MAX_INCLUDE_CACHE_SIZE=0 (auto configured)
GOMA_MAX_POOLED_INCLUDE_DIR_CACHE=512 (auto configured)
GOMA_USE_SSL=true`; got != want {
		t.Errorf("cpl.GomaFlags=%q; want=%q", got, want)
	}
	if got, want := cpl.GomaLimits, "max incoming: 1339 max_nfile=4096 FD_SETSIZE=1024 max_num_sockets=4096 USE_EPOLL=1 threads=12+3"; got != want {
		t.Errorf("cpl.GomaLimits=%q, want=%q", got, want)
	}
	if got, want := cpl.CrashDump, ""; got != want {
		t.Errorf("cpl.CrashDump=%q, want=%q", got, want)
	}
	if got, want := cpl.Stats, "request: total=0 success=0 failure=0"; got != want {
		t.Errorf("cpl.Stats=%q, want=%q", got, want)
	}
	if got, want := cpl.Histogram, `ThreadpoolHttpServerRequestSize:  Basic stats: count: 4 min: 124 max: 232 mean: 178 stddev: 53
[ 64-128]: ##################################################2
[128-256]: ##################################################2

ThreadpoolHttpServerResponseSize:  Basic stats: count: 4 min: 21 max: 96 mean: 69 stddev: 28
[16- 32]: ################1
[32- 64]:
[64-128]: ##################################################3`; got != want {
		t.Errorf("cpl.Histogram=%q, want=%q", got, want)
	}

	const buildID = "6235ce6e-d8e4-4e17-a9cf-e702a816834c"

	wants := map[string]struct {
		Desc        string
		CompileMode CompileMode
		AcceptTime  time.Time
		StartTime   time.Time
		EndTime     time.Time
		NumLogs     int
		Response    string
	}{
		"0": {
			Desc:        "../../third_party/webrtc/system_wrappers/source/condition_variable_posix.cc gomacc_pid=5838",
			CompileMode: Compiling,
			AcceptTime:  timeAt("2014/09/11 17:44:06.493170"),
			StartTime:   timeAt("2014/09/11 17:44:06.493176"),
			EndTime:     timeAt("2014/09/11 17:44:13.786922"),
			NumLogs:     5,
			Response:    "local finish, no goma",
		},
		"1": {
			Desc:        "../../third_party/webrtc/common_audio/signal_processing/filter_ma_fast_q12.c gomacc_pid=5840",
			CompileMode: Compiling,
			AcceptTime:  timeAt("2014/09/11 17:44:06.493980"),
			StartTime:   timeAt("2014/09/11 17:44:06.493988"),
			EndTime:     timeAt("2014/09/11 17:44:16.738234"),
			NumLogs:     6,
			Response:    "local finish, abort goma",
		},
		"2": {
			Desc:        "../../third_party/lzma_sdk/7zBuf.c gomacc_pid=5842",
			CompileMode: Compiling,
			AcceptTime:  timeAt("2014/09/11 17:44:06.494810"),
			StartTime:   timeAt("2014/09/11 17:44:06.494817"),
			EndTime:     timeAt("2014/09/11 17:44:16.700889"),
			NumLogs:     6,
			Response:    "local finish, abort goma",
		},
		"3": {
			Desc:        "../../third_party/yasm/source/patched-yasm/tools/genmacro/genmacro.c gomacc_pid=5845",
			CompileMode: Compiling,
			AcceptTime:  timeAt("2014/09/11 17:44:06.495700"),
			StartTime:   timeAt("2014/09/11 17:44:06.495704"),
			EndTime:     timeAt("2014/09/11 17:44:16.667989"),
			NumLogs:     6,
			Response:    "local finish, abort goma",
		},
		"4": {
			Desc:        "gen/ui/resources/grit/ui_resources_map.cc gomacc_pid=5848",
			CompileMode: Compiling,
			AcceptTime:  timeAt("2014/09/11 17:44:06.496720"),
			StartTime:   timeAt("2014/09/11 17:44:06.496722"),
			EndTime:     timeAt("2014/09/11 17:44:13.874645"),
			NumLogs:     5,
			Response:    "goma success",
		},
		"5": {
			Desc:        "./dump_syms /search/search.cc gomacc_pid=5850",
			CompileMode: Linking,
			AcceptTime:  timeAt("2014/09/11 17:44:06.497630"),
			StartTime:   timeAt("2014/09/11 17:44:06.497638"),
			EndTime:     timeAt("2014/09/11 17:44:16.601634"),
			NumLogs:     6,
			Response:    "should fallback",
		},
		"6": {
			Desc:        "../../components/search/search_switches.cc gomacc_pid=5852",
			CompileMode: Compiling,
			AcceptTime:  timeAt("2014/09/11 17:44:06.498120"),
			StartTime:   timeAt("2014/09/11 17:44:06.498575"),
			EndTime:     timeAt("2014/09/11 17:44:16.879138"),
			NumLogs:     7,
			Response:    "local finish, abort goma",
		},
	}
	for id, want := range wants {
		got := cpl.tasks[id]
		if got == nil {
			t.Errorf("%s: got=<nil>, want=%v", id, want)
			continue
		}
		if got.BuildID != buildID {
			t.Errorf("%s: BuildID=%q; want=%q", id, got.BuildID, buildID)
		}
		if got.Desc != want.Desc {
			t.Errorf("%s: Desc=%q; want=%q", id, got.Desc, want.Desc)
		}
		if got.CompileMode != want.CompileMode {
			t.Errorf("%s: CompileMode=%v; want=%v", id, got.CompileMode, want.CompileMode)
		}
		if got.AcceptTime != want.AcceptTime {
			t.Errorf("%s: AcceptTime=%v; want=%v", id, got.AcceptTime, want.AcceptTime)
		}
		if got.StartTime != want.StartTime {
			t.Errorf("%s: StartTime=%v; want=%v", id, got.StartTime, want.StartTime)
		}
		if got.EndTime != want.EndTime {
			t.Errorf("%s: EndTime=%v; want=%v", id, got.EndTime, want.EndTime)
		}
		if len(got.Logs) != want.NumLogs {
			t.Errorf("%s: len(Logs)=%d; want=%d; %v", id, len(got.Logs), want.NumLogs, got.Logs)
		}
		if got.Response != want.Response {
			t.Errorf("%s: Response=%q; want=%q", id, got.Response, want.Response)
		}
	}
}

func TestParseHTTPError(t *testing.T) {
	logcontent := `Running on machine: gce-trusty-e833d7b0-us-west1-a-n0n5
Log line format: [IWEF]mmdd hh:mm:ss.uuuuuu threadid file:line] msg
I0325 20:39:59.901118 25832 compile_service.cc:123] Task:861 build_id:6235ce6e-d8e4-4e17-a9cf-e702a816834c
I0325 20:40:01.027500 25514 compile_task.cc:462] Task:861 Start gen/third_party/blink/renderer/core/css/properties/longhands/text_decoration_color.cc gomacc_pid=20502 build_dir=/b/s/w/ir/cache/builder/src/out/Release
I0325 20:40:01.031714 25514 compile_task.cc:559] Task:861 GOMA_USE_LOCAL=false
I0325 20:40:01.031783 25514 compile_task.cc:2696] Task:861 fill compiler info cache_hit=1 updated=0 state=0x7f1cb08ad8c0 in 49.901us
I0325 20:40:01.095594 25514 compile_task.cc:3169] Task:861 use deps cache. required_files=1198
I0325 20:40:02.107694 25831 compile_service.cc:123] Task:884 build_id:6235ce6e-d8e4-4e17-a9cf-e702a816834c
I0325 20:40:02.109047 25514 compile_task.cc:462] Task:884 Start ../../third_party/blink/renderer/core/layout/layout_text_control_multi_line.cc gomacc_pid=20591 build_dir=/b/s/w/ir/cache/builder/src/out/Release
I0325 20:40:02.109117 25514 compile_task.cc:559] Task:884 GOMA_USE_LOCAL=false
I0325 20:40:02.109182 25514 compile_task.cc:2696] Task:884 fill compiler info cache_hit=1 updated=0 state=0x7f1cb08ad8c0 in 52.86us
I0325 20:40:02.122812 25514 compile_task.cc:3169] Task:884 use deps cache. required_files=1406
W0325 20:42:22.691454 25514 http.cc:1910] Task:861 read  http=502 path=/cxx-compiler-service/e Details:HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/html; charset=UTF-8\r\nReferrer-Policy: no-referrer\r\nContent-Length: 332\r\nDate: Tue, 26 Mar 2019 03:42:22 GMT\r\nAlt-Svc: clear\r\n\r\n\n<html><head>\n<meta http-equiv=\"content-type\" content=\"text/html;charset=utf-8\">\n<title>502 Server Error</title>\n</head>\n<body text=#000000 bgcolor=#ffffff>\n<h1>Error: Server Error</h1>\n<h2>The server encountered a temporary error and could not complete your request.<p>Please try again in 30 seconds.</h2>\n<h2></h2>\n</body></html>\n
I0325 20:42:22.691567 25514 http.cc:1441] UpdateBackoff error 500ms -> 700ms
W0325 20:42:22.691599 25514 compile_task.cc:1109] Task:861 rpc err=-1  failed Got HTTP error:502
W0325 20:42:22.691634 25514 compile_task.cc:4376] Task:861 no retry: exec error=0 retry=0 reason=RPC failed http=502: Got HTTP error:502 http=unhealthy
I0325 20:42:22.691656 25514 compile_task.cc:1555] Task:861 finished fail in call exec state=CALL_EXEC abort=0 canceled=0
W0325 20:42:23.513343 25514 http.cc:1910] Task:884 read  http=502 path=/cxx-compiler-service/e Details:HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/html; charset=UTF-8\r\nReferrer-Policy: no-referrer\r\nContent-Length: 332\r\nDate: Tue, 26 Mar 2019 03:42:23 GMT\r\nAlt-Svc: clear\r\n\r\n\n<html><head>\n<meta http-equiv=\"content-type\" content=\"text/html;charset=utf-8\">\n<title>502 Server Error</title>\n</head>\n<body text=#000000 bgcolor=#ffffff>\n<h1>Error: Server Error</h1>\n<h2>The server encountered a temporary error and could not complete your request.<p>Please try again in 30 seconds.</h2>\n<h2></h2>\n</body></html>\n
I0325 20:42:23.517006 25514 http.cc:1441] UpdateBackoff error 700ms -> 980ms
W0325 20:42:23.517045 25514 compile_task.cc:1109] Task:884 rpc err=-1  failed Got HTTP error:502
W0325 20:42:23.517076 25514 compile_task.cc:4376] Task:884 no retry: exec error=0 retry=0 reason=RPC failed http=502: Got HTTP error:502 http=unhealthy
I0325 20:42:23.517096 25514 compile_task.cc:1555] Task:884 finished fail in call exec state=CALL_EXEC abort=0 canceled=0
I0325 20:42:41.854074 25514 compile_task.cc:2102] Task:861 ReplyResponse: fail fallback
I0325 20:42:41.854221 25514 compile_task.cc:2308] Task:861 remove deps cache entry.
I0325 20:42:41.857728 25514 compile_task.cc:2102] Task:884 ReplyResponse: fail fallback
I0325 20:42:41.857782 25514 compile_task.cc:2308] Task:884 remove deps cache entry.
`
	cpl, err := Parse("compiler_proxy.INFO", strings.NewReader(logcontent))
	if err != nil {
		t.Fatalf(`Parse("compiler_proxy.INFO")=%v, %v; want=_, <nil>`, cpl, err)
	}
	want := map[HTTPError][]string{
		{
			Op:   "read",
			Code: 502,
			Resp: `path=/cxx-compiler-service/e Details:HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/html; charset=UTF-8\r\nReferrer-Policy: no-referrer\r\nContent-Length: 332\r\nAlt-Svc: clear\r\n\r\n\n<html><head>\n<meta http-equiv=\"content-type\" content=\"text/html;charset=utf-8\">\n<title>502 Server Error</title>\n</head>\n<body text=#000000 bgcolor=#ffffff>\n<h1>Error: Server Error</h1>\n<h2>The server encountered a temporary error and could not complete your request.<p>Please try again in 30 seconds.</h2>\n<h2></h2>\n</body></html>\n`,
		}: {"861", "884"},
	}
	if diff := cmp.Diff(want, cpl.HTTPErrors); diff != "" {
		t.Errorf("cpl.HTTPErrors; diff -want +got\n%s", diff)
	}
}

func TestDurationDistribution(t *testing.T) {
	st := timeAt("2014/09/11 17:43:51.000000")

	tl := []*TaskLog{
		{
			ID:        "1",
			StartTime: st.Add(1 * time.Second),
			EndTime:   st.Add(2 * time.Second),
		},
		{
			ID:        "2",
			StartTime: st.Add(2 * time.Second),
			EndTime:   st.Add(4 * time.Second),
		},
		{
			ID:        "3",
			StartTime: st.Add(3 * time.Second),
			EndTime:   st.Add(4 * time.Second),
		},
		{
			ID:        "4",
			StartTime: st.Add(4 * time.Second),
			EndTime:   st.Add(5 * time.Second),
		},
		{
			ID:        "5",
			StartTime: st.Add(5 * time.Second),
			EndTime:   st.Add(8 * time.Second),
		},
		{
			ID:        "6",
			StartTime: st.Add(6 * time.Second),
			EndTime:   st.Add(7 * time.Second),
		},
	}
	// 0-1: 0 task
	// 1-2: 1 task "1"
	// 2-3: 1 task "2"
	// 3-4: 2 tasks "2", "3"
	// 4-5: 1 task "4"
	// 5-6: 1 task "5"
	// 6-7: 2 tasks "5", "6"
	// 7-8: 1 task "5"
	//=>
	// 0 task: 1 sec
	// 1 task: 5 secs
	// 2 tasks: 2 secs
	got := DurationDistribution(st, tl)
	want := []time.Duration{
		1 * time.Second,
		5 * time.Second,
		2 * time.Second,
	}
	if len(got) != len(want) {
		t.Logf("got=%v, want=%v", got, want)
		t.Fatalf("max jobs=%d; want=%d", len(got), len(want))
	}
	for i, d := range got {
		if d != want[i] {
			t.Errorf("%d: %v; want=%v", i, d, want[i])
		}
	}
}
