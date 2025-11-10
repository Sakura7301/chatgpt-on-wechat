#!/bin/bash

unset KUBECONFIG

cd .. && docker build -f docker/Dockerfile.latest \
             -t sakura7301/chatgpt-on-wechat .

docker tag sakura7301/chatgpt-on-wechat sakura7301/chatgpt-on-wechat:$(date +%y%m%d)