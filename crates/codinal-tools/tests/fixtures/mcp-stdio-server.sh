#!/bin/sh
set -eu

IFS= read -r request
case "$request" in *'"jsonrpc":"2.0"'*) ;; *) exit 2 ;; esac
case "$request" in *'"id":1'*) ;; *) exit 2 ;; esac
case "$request" in *'"method":"tools/list"'*) ;; *) exit 2 ;; esac

printf '%s\n' '{"jsonrpc":"2.0","id":1,"result":{"server":"codinal-fixture","tools":[]}}'
