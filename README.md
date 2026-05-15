# nats-austral

NATS client for Austral with a safety-first API based on Linear types, Typeclasses,
Safe Arithmetic, and Algebraic Data Types.

## Goals

- No garbage collection.
- No destructors.
- No exceptions or surprise control flow.
- No implicit function calls or implicit type conversions.
- No global state.
- No subtyping, macros, reflection, or Java-style annotations.
- No first-class async.
- No arithmetic precedence in client logic; use explicit safe arithmetic methods.
- No variable shadowing.

## Modules

- `src/Nats/Client.aui`: public client interface.
- `src/Nats/Client.aum`: reference implementation and C NATS FFI boundary.
- `examples/Subscribe.aum`: minimal subscribe flow.
- `docs/DESIGN.md`: lifecycle and safety design.

## Linear event policy

Every inbound NATS event is represented as a Linear `Event` inside the client
module. The `subscribe` function copies the payload into the internal state of
the Linear `Client`, then consumes the event at the module boundary. Application
code therefore does not need, and cannot forget, an explicit event-destroy call.

## Tests

Run the source-level contract tests with:

```sh
python3 -m pytest
```

The tests verify the Linear event lifecycle, Typeclass and ADT declarations,
safe arithmetic usage, and absence of forbidden runtime constructs in the
Austral sources.

## Build status

This repository is a source-level Austral implementation. The current container
does not include the Austral compiler, so syntax and integration checks are
limited to repository-level validation unless `austral` is installed.

## Zig server prototype

Veja `natzig/` para uma implementação de servidor NATS em Zig e testes com client NATS existente (`nats-py`).
