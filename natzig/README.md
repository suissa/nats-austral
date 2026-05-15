# natzig

Servidor NATS minimalista escrito puramente em Zig, com suporte suficiente para
clientes NATS padrão se conectarem e trocarem mensagens.

## Recursos implementados

- `INFO` no handshake.
- `CONNECT`.
- `PING`/`PONG`.
- `SUB` / `UNSUB`.
- `PUB` com entrega para assinantes (`MSG`).

## Como executar

```bash
zig run src/main.zig
```

Servidor escuta em `127.0.0.1:4222`.

## Testes com client existente

Os testes de integração usam o client Python oficial/comunitário `nats-py`:

```bash
pip install nats-py pytest pytest-asyncio
pytest natzig/tests/test_natzig_with_nats_py.py
```

> Observação: em ambientes sem `zig` instalado, o teste é marcado como `skip`.
