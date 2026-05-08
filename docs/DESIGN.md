# NATS Austral client design

This repository implements a NATS client surface that follows Austral's safety model:

- **Linear client capability**: `Client` is linear, so connection ownership cannot be duplicated, dropped, used after close, or closed twice.
- **Linear events**: `Event` is linear and private to the module body. The public `subscribe` API does not leak it.
- **Automatic event disposal at the subscribe boundary**: `subscribe` wraps an inbound native NATS message as `Event`, copies its payload into the client's internal inbox, and consumes the event inside the module before returning to application code. Users never write an explicit `destroyEvent(event)` call.
- **Typeclasses**: `Encodable`, `Decodable`, and `HandlesMessage` provide bounded ad-hoc polymorphism without unconstrained overloading.
- **Safe arithmetic**: inbox accounting uses Austral's `TrappingArithmetic.trappingAdd` instead of unqualified arithmetic operators.
- **Algebraic data types**: `NatsResult`, `NatsError`, and `MessageKind` model success, failure, and message variants without exceptions.

The implementation is intentionally explicit: no global mutable state, no exceptions, no destructors, no implicit conversions, no reflection, no macros, and no hidden async control flow.

## Event lifecycle

```text
native NATS message
        |
        v
Linear Event (module-private)
        |
        | copy payload bytes into Client inbox
        v
Client with stored payload snapshot
        |
        | consume Event by destructuring in module body
        v
user handler sees Client state, not Event ownership
```

Because `Event` is linear and opaque/private, any backend implementation must consume it exactly once. The `subscribe` function is the trust boundary that ensures the event cannot escape and cannot be forgotten.

## Native backend notes

`src/Nats/Client.aum` declares FFI entry points for the C NATS client. A production build should link against `nats.c` and replace the reference payload-copy stub with a fixed-capacity ring buffer implementation using region or manually allocated storage.
