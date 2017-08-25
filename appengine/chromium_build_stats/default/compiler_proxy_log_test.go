// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package chromiumbuildstats

import (
	"net/http/httptest"
	"strings"
	"testing"

	"compilerproxylog"
)

func TestCompilerProxyLogSummary(t *testing.T) {
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
I0911 17:44:06.493176  5786 compile_task.cc:923] Task:0 Start ../../third_party/webrtc/system_wrappers/source/condition_variable_posix.cc gomacc_pid=5838
I0911 17:44:06.493830  5798 subprocess_task.cc:244] ../../third_party/llvm-build/Release+Asserts/bin/clang++ started pid=5844 state=RUN
I0911 17:44:06.493988  5787 compile_task.cc:923] Task:1 Start ../../third_party/webrtc/common_audio/signal_processing/filter_ma_fast_q12.c gomacc_pid=5840
I0911 17:44:06.494817  5788 compile_task.cc:923] Task:2 Start ../../third_party/lzma_sdk/7zBuf.c gomacc_pid=5842
I0911 17:44:06.495704  5790 compile_task.cc:923] Task:3 Start ../../third_party/yasm/source/patched-yasm/tools/genmacro/genmacro.c gomacc_pid=5845
I0911 17:44:06.496722  5792 compile_task.cc:923] Task:4 Start gen/ui/resources/grit/ui_resources_map.cc gomacc_pid=5848
I0911 17:44:06.497638  5794 compile_task.cc:923] Task:5 Start linking ./dump_syms /search/search.cc gomacc_pid=5850
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
	cpl, err := compilerproxylog.Parse("compiler_proxy.INFO", strings.NewReader(logcontent))
	if err != nil {
		t.Fatalf(`Parse("compiler_proxy.INFO")=%v, %v; want=_, <nil>`, cpl, err)
	}
	res := httptest.NewRecorder()
	compilerProxyLogSummary(res, "", cpl)

	if got, want := res.Body.String(), `
<html>
<head>
 <title></title>
</head>
<body>
<h1><a href="/file/"></a></h1>
<table>
<tr><th>Filename <td>compiler_proxy.INFO
<tr><th>Created <td>2014-09-11 17:43:51 &#43;0000 UTC
<tr><th>Machine <td>chromeperf58
<tr><th>GomaRevision <td>4a694601289a8f07a6d6439631049e1ad0914dfb@1409795845
<tr><th>GomaVersion <td>68
<tr><th>GomaFlags <td><pre>GOMA_API_KEY_FILE=/b/build/goma/goma.key
GOMA_COMPILER_PROXY_DAEMON_MODE=true
GOMA_COMPILER_PROXY_HTTP_THREADS=3 (auto configured)
GOMA_COMPILER_PROXY_THREADS=12 (auto configured)
GOMA_MAX_INCLUDE_CACHE_SIZE=0 (auto configured)
GOMA_MAX_POOLED_INCLUDE_DIR_CACHE=512 (auto configured)
GOMA_USE_SSL=true</pre>
<tr><th>GomaLimits <td>max incoming: 1339 max_nfile=4096 FD_SETSIZE=1024 max_num_sockets=4096 USE_EPOLL=1 threads=12&#43;3
<tr><th>CrashDump <td>
<tr><th>Stats <td><pre>request: total=0 success=0 failure=0</pre>
<tr><th>Duration <td>1772h49m5.480244s
<tr><th>Tasks <td>7
<tr><th>TasksPerSec <td>1.0968098457906632e-06
</table>


<h2>compiling: # of tasks: 6</h2>
<table>
 <tr><th colspan=2>replices
 <tr><th>goma success<td>1
 <tr><th>local finish, abort goma<td>4
 <tr><th>local finish, no goma<td>1
 <tr><th colspan=2>duration
 <tr><th>average <td>9.2792145s
 <tr><th>Max     <td>10.381015s
  <tr><th>98 <td>10.381015s
  <tr><th>91 <td>10.381015s
  <tr><th>75 <td>10.244246s
  <tr><th>50 <td>10.172285s
  <tr><th>25 <td>7.377923s
  <tr><th>9 <td>7.293746s
  <tr><th>2 <td>7.293746s
 <tr><th>Min     <td>7.293746s
 <tr><th colspan=2>log tasks
  <tr><td>0 Task:6<td>10.381015s
   <td>../../components/search/search_switches.cc gomacc_pid=5852
   <td>local finish, abort goma
  <tr><td>1 Task:1<td>10.244246s
   <td>../../third_party/webrtc/common_audio/signal_processing/filter_ma_fast_q12.c gomacc_pid=5840
   <td>local finish, abort goma
  <tr><td>2 Task:2<td>10.206072s
   <td>../../third_party/lzma_sdk/7zBuf.c gomacc_pid=5842
   <td>local finish, abort goma
  <tr><td>3 Task:3<td>10.172285s
   <td>../../third_party/yasm/source/patched-yasm/tools/genmacro/genmacro.c gomacc_pid=5845
   <td>local finish, abort goma
  <tr><td>4 Task:4<td>7.377923s
   <td>gen/ui/resources/grit/ui_resources_map.cc gomacc_pid=5848
   <td>goma success
  <tr><td>5 Task:0<td>7.293746s
   <td>../../third_party/webrtc/system_wrappers/source/condition_variable_posix.cc gomacc_pid=5838
   <td>local finish, no goma
</table>

<h2>precompiling: # of tasks: 0</h2>
<table>
 <tr><th colspan=2>replices
 <tr><th colspan=2>duration
 <tr><th>average <td>0s
 <tr><th>Max     <td>0s
 <tr><th>Min     <td>0s
 <tr><th colspan=2>log tasks
</table>

<h2>linking: # of tasks: 1</h2>
<table>
 <tr><th colspan=2>replices
 <tr><th>should fallback<td>1
 <tr><th colspan=2>duration
 <tr><th>average <td>10.103996s
 <tr><th>Max     <td>10.103996s
  <tr><th>98 <td>10.103996s
  <tr><th>91 <td>10.103996s
  <tr><th>75 <td>10.103996s
  <tr><th>50 <td>10.103996s
  <tr><th>25 <td>10.103996s
  <tr><th>9 <td>10.103996s
  <tr><th>2 <td>10.103996s
 <tr><th>Min     <td>10.103996s
 <tr><th colspan=2>log tasks
  <tr><td>0 Task:5<td>10.103996s
   <td>./dump_syms /search/search.cc gomacc_pid=5850
   <td>should fallback
</table>


<h2>Duration per num active tasks</h2>
<table>
<tr><th># of tasks <th>duration <th> cumulative duration

 <tr><td>0 <td>15.493176s <td>15.493176s

 <tr><td>1 <td>141.716ms <td>15.634892s

 <tr><td>2 <td>38.174ms <td>15.673066s

 <tr><td>3 <td>33.787ms <td>15.706853s

 <tr><td>4 <td>67.373ms <td>15.774226s

 <tr><td>5 <td>2.727905s <td>18.502131s

 <tr><td>6 <td>88.66ms <td>18.590791s

 <tr><td>7 <td>7.288347s <td>25.879138s

</table>

<h2>Compiler Proxy Histogram</h2>
<pre>ThreadpoolHttpServerRequestSize:  Basic stats: count: 4 min: 124 max: 232 mean: 178 stddev: 53
[ 64-128]: ##################################################2
[128-256]: ##################################################2

ThreadpoolHttpServerResponseSize:  Basic stats: count: 4 min: 21 max: 96 mean: 69 stddev: 28
[16- 32]: ################1
[32- 64]:
[64-128]: ##################################################3</pre>

</body>
</html>
`; got != want {
		t.Errorf("compilerProxyLogSummary(_, _, _) writes %s; want %s", got, want)
	}
}
