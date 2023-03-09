local ldap = require("resty.ffi.ldap")

return function()
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

    ngx.say("ok")
end
