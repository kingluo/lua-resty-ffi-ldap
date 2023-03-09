#
# Copyright (c) 2023, Jinhua Luo (kingluo) luajit.io@gmail.com
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
from cffi import FFI
ffi = FFI()
ffi.cdef("""
void* malloc(size_t);
void *memcpy(void *dest, const void *src, size_t n);
void* ngx_http_lua_ffi_task_poll(void *p);
char* ngx_http_lua_ffi_get_req(void *tsk, int *len);
void ngx_http_lua_ffi_respond(void *tsk, int rc, char* rsp, int rsp_len);
""")
C = ffi.dlopen(None)

import threading
import json
import asyncio
import traceback
import bonsai
from bonsai.asyncio import AIOConnectionPool

NEW_CLIENT=1
CLOSE_CLIENT=2
SEARCH=3

class State:
    def __init__(self, cfg):
        self.clients = {}
        self.idx = 0
        self.loop = asyncio.new_event_loop()
        t = threading.Thread(target=self.loop.run_forever)
        t.daemon = True
        t.start()
        self.event_loop_thread = t

    async def close_client(self, req, task):
        try:
            idx = req["client"]
            client = self.clients[idx]
            del self.clients[idx]
            await client.close()
            C.ngx_http_lua_ffi_respond(task, 0, ffi.NULL, 0)
        except Exception as exc:
            tb = traceback.format_exc()
            print(tb)
            tb = f"{exc}"
            res = C.malloc(len(tb))
            C.memcpy(res, tb.encode(), len(tb))
            C.ngx_http_lua_ffi_respond(task, 1, res, 0)

    async def new_client(self, req, task):
        try:
            self.idx += 1
            idx = self.idx
            client = bonsai.LDAPClient(req["url"])
            client.set_credentials(**req["auth"])
            pool = AIOConnectionPool(client=client, maxconn=req["maxconn"], timeout=3)
            await pool.open()

            #conn = await pool.get()
            #print(await conn.whoami())
            #await pool.put(conn)

            self.clients[idx] = pool
            data = json.dumps({"client":idx})
            res = C.malloc(len(data))
            C.memcpy(res, data.encode(), len(data))
            C.ngx_http_lua_ffi_respond(task, 0, res, len(data))
        except Exception as exc:
            tb = traceback.format_exc()
            print(tb)
            tb = f"{exc}"
            res = C.malloc(len(tb))
            C.memcpy(res, tb.encode(), len(tb))
            C.ngx_http_lua_ffi_respond(task, 1, res, 0)

    async def search(self, req, task):
        try:
            idx = req["client"]
            pool = self.clients[idx]
            conn = await pool.get()
            res = await conn.search(**req["search"])
            await pool.put(conn)
            ents = []
            for ent in res:
                item = {}
                for (k, v) in ent.items():
                    if k == 'dn':
                        item['dn'] = v.__str__()
                    else:
                        item[k] = v
                ents.append(item)
            data = json.dumps(ents)
            res = C.malloc(len(data))
            C.memcpy(res, data.encode(), len(data))
            C.ngx_http_lua_ffi_respond(task, 0, res, len(data))
        except Exception as exc:
            tb = traceback.format_exc()
            print(tb)
            tb = f"{exc}"
            res = C.malloc(len(tb))
            C.memcpy(res, tb.encode(), len(tb))
            C.ngx_http_lua_ffi_respond(task, 1, res, 0)

    async def close(self, req, task):
        for (_, client) in self.clients:
            await client.close()
        self.loop.stop()

    def poll(self, tq):
        while True:
            task = C.ngx_http_lua_ffi_task_poll(ffi.cast("void*", tq))
            if task == ffi.NULL:
                asyncio.run_coroutine_threadsafe(self.close(req, task), self.loop)
                self.event_loop_thread.join()
                break
            r = C.ngx_http_lua_ffi_get_req(task, ffi.NULL)
            req = json.loads(ffi.string(r))
            cmd = req["cmd"]
            if cmd == NEW_CLIENT:
                asyncio.run_coroutine_threadsafe(self.new_client(req, task), self.loop)
            elif cmd == SEARCH:
                asyncio.run_coroutine_threadsafe(self.search(req, task), self.loop)
            elif cmd == CLOSE_CLIENT:
                asyncio.run_coroutine_threadsafe(self.close_client(req, task), self.loop)

def init(cfg, tq):
    data = ffi.string(ffi.cast("char*", cfg))
    cfg = json.loads(data)
    st = State(cfg)
    t = threading.Thread(target=st.poll, args=(tq,))
    t.daemon = True
    t.start()
    return 0
