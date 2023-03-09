# lua-resty-ffi-ldap

The openresty ldap client library that encapsulates [bonsai](https://github.com/noirello/bonsai).

## Background

LDAP is commonly used to do authentication and authorization.

But OpenResty does not have a fully functional LDAP library.

Let's have a look at the current alternatives:

* [lualdap](https://lualdap.github.io/lualdap/manual/)
  * No SASL auth, simple bind only
  * Not based on cosocket, i.e. not async
* [lua-resty-ldap](https://github.com/api7/lua-resty-ldap)
  * No SASL auth, simple bind only

What about other programming lanuages?

* [go-ldap](https://github.com/go-ldap/ldap)
  * [No GSSAPI/Kerberos support](https://github.com/go-ldap/ldap/pull/340#issuecomment-1460021435)
* [rust-ldap3](https://github.com/inejge/ldap3)
  * depends on `kinit` to get service ticket first
  * no keytab, no ad-hoc credential support
* [python-ldap](https://www.python-ldap.org/en/python-ldap-3.4.3/reference/ldap-sasl.html#ldap.sasl.gssapi)
  * depends on `kinit` to get service ticket first
  * no keytab, no ad-hoc credential support
  * not async

After investigation, I think [bonsai](https://bonsai.readthedocs.io/en/latest/index.html) is the best choice,
which is a popular and active python ldap client library.

Highlights:

* asyncio support
* keytab, ad-hoc credential support
* simple pythonic design
* based on robust and time-tested C libraries, e.g. libldap2, libsasl2, libkrb5

Why not encapsulate it so that we could reuse it in openresty?

[lua-resty-ffi](https://github.com/kingluo/lua-resty-ffi) provides an efficient and generic API to do hybrid programming
in openresty with mainstream languages (Go, Python, Java, Rust, Nodejs).

`lua-resty-ffi-ldap = lua-resty-ffi + bonsai`

I already tested this library on:

* openldap + MIT KDC
* Windows AD (Kerberos enabled)

## Synopsis

```lua
local ldap = require("resty.ffi.ldap")

local client = ldap.new({
    url = "ldap://bonsai.test",
    maxconn = 2,
    auth = {
        mechanism="GSSAPI",
        user="chuck",
        password="Foo2023@",
        realm="BONSAI.TEST",
    }
})
assert(client)

local ok, res = client:search({
    base = "cn=chuck,dc=bonsai,dc=test",
    scope = ldap.SCOPE_SUB,
    filter_exp = "(objectclass=user)",
    attrlist = {'memberOf', 'sAMAccountName'},
})
assert(ok)
res = res[1]
assert(res.dn == "CN=chuck,DC=bonsai,DC=test", "dn mismatch")
assert(res.memberOf[1] == "CN=foobar,DC=bonsai,DC=test", "memberOf mismatch")
assert(res.sAMAccountName[1] == "chuck", "sAMAccountName mismatch")

local ok = client:close()
assert(ok)
```

## Demo

```bash
# install lua-resty-ffi
# https://github.com/kingluo/lua-resty-ffi#install-lua-resty-ffi-via-luarocks
# set `OR_SRC` to your openresty source path
luarocks config variables.OR_SRC /tmp/tmp.Z2UhJbO1Si/openresty-1.21.4.1
luarocks install lua-resty-ffi

# make lua-resty-ffi python loader library
apt install python3-dev python3-pip libffi-dev
cd /opt
git clone https://github.com/kingluo/lua-resty-ffi
cd /opt/lua-resty-ffi/examples/python
make

apt install libldap2-dev libsasl2-dev heimdal-dev

pip3 install bonsai

cd /opt
git clone https://github.com/kingluo/lua-resty-ffi-ldap

cd /opt/lua-resty-ffi-ldap/demo

# run nginx
KRB5_CONFIG="$PWD/krb5.conf" \
LD_LIBRARY_PATH=/opt/lua-resty-ffi/examples/python:/usr/local/lib/lua/5.1 \
PYTHONPATH=/opt/lua-resty-ffi-ldap \
nginx -p $PWD -c nginx.conf

# set up a Windows AD...

# in another terminal, trigger demo
curl localhost:20000/demo
```
