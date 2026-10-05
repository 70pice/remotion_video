# 字节配音的 Windows TUN 连接问题

2026-10-05，任务 `6fde472d00444b26aaa86ce680a9c7f3` 的配音停在 `connecting`，正文尚未提交。无 Key、无正文的对照探测显示：同一官方服务 IP、域名和证书校验，默认 YouTu TUN 出口返回 `SSLEOFError / UNEXPECTED_EOF_WHILE_READING`；指定以太网 socket 出口后 TLS 建立成功，能够收到 HTTP 响应。这证明当前 TUN 路径存在连接问题，不代表音色或 API Key 过期。

`byte_ws_voice.py` 保留正常默认连接。仅遇到 `SSLEOFError` 时，在 Windows 只读查询具有 IPv4 默认路由的活动物理网卡，再为同一个官方公网地址创建一次指定出口的 socket。通过 Winsock `IP_UNICAST_IF` 设置网络字节序的接口索引，仍使用原官方 WSS 地址、SNI 和完整证书校验。查询与连接共享原超时预算。

这个处理只影响配音连接，不更改全局代理、TUN、DNS 或路由表，不将接口索引写死为本机值。证书验证失败、HTTP 鉴权被拒绝及正文提交后的异常都不会触发该出口重试。正文提交后继续保存 `UNKNOWN` 并阻止自动再次付费。

操作记录将 TLS 失败标为 `failure_category=tls_handshake`；握手收到 HTTP 拒绝标为 `handshake_rejected`，保留数字状态。待办提示区分连接失败与鉴权/权限检查，不记录异常原文、响应正文或请求凭证。没有带鉴权的真实成功会话时，不能声称 Key 和音色已经有效。

参考：[字节官方双向流式接口](https://docs.volcengine.com/docs/DoubaoVoice/WebSocketBidirectionalStreaming-V3?lang=zh)、[Microsoft IPPROTO_IP socket 选项](https://learn.microsoft.com/en-us/windows/win32/winsock/ipproto-ip-socket-options)。
