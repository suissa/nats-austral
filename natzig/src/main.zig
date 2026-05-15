const std = @import("std");

const Allocator = std.mem.Allocator;

const Subscription = struct {
    conn_index: usize,
    sid: []u8,
};

const ClientState = struct {
    socket: std.net.Stream,
    pending_bytes: ?usize = null,
    pending_subject: ?[]u8 = null,
    pending_reply_to: ?[]u8 = null,
    line_buf: std.ArrayList(u8),

    pub fn init(allocator: Allocator, socket: std.net.Stream) ClientState {
        return .{ .socket = socket, .line_buf = std.ArrayList(u8).init(allocator) };
    }

    pub fn deinit(self: *ClientState, allocator: Allocator) void {
        if (self.pending_subject) |s| allocator.free(s);
        if (self.pending_reply_to) |r| allocator.free(r);
        self.line_buf.deinit();
        self.socket.close();
    }
};

fn send(stream: std.net.Stream, data: []const u8) !void {
    try stream.writeAll(data);
}

fn splitSpaces(line: []const u8) [6][]const u8 {
    var out: [6][]const u8 = .{ "", "", "", "", "", "" };
    var it = std.mem.tokenizeScalar(u8, line, ' ');
    var i: usize = 0;
    while (it.next()) |tok| : (i += 1) {
        if (i >= out.len) break;
        out[i] = tok;
    }
    return out;
}

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const addr = try std.net.Address.parseIp4("127.0.0.1", 4222);
    var listener = try addr.listen(.{ .reuse_address = true });
    defer listener.deinit();

    std.debug.print("natzig listening on 127.0.0.1:4222\n", .{});

    var clients = std.ArrayList(ClientState).init(allocator);
    defer {
        for (clients.items) |*client| client.deinit(allocator);
        clients.deinit();
    }

    var subscriptions = std.StringHashMap(std.ArrayList(Subscription)).init(allocator);
    defer {
        var it = subscriptions.iterator();
        while (it.next()) |entry| {
            allocator.free(entry.key_ptr.*);
            for (entry.value_ptr.items) |sub| allocator.free(sub.sid);
            entry.value_ptr.deinit();
        }
        subscriptions.deinit();
    }

    while (true) {
        if (clients.items.len < 64) {
            if (listener.accept()) |conn| {
                const stream = conn.stream;
                try send(stream, "INFO {\"server_id\":\"natzig\",\"version\":\"0.1.0\",\"go\":\"zig\",\"host\":\"127.0.0.1\",\"port\":4222,\"max_payload\":1048576,\"proto\":1}\r\n");
                try clients.append(ClientState.init(allocator, stream));
            } else |_| {}
        }

        var i: usize = 0;
        while (i < clients.items.len) {
            var dead = false;
            var client = &clients.items[i];
            var tmp: [2048]u8 = undefined;

            const read_n = client.socket.read(&tmp) catch {
                dead = true;
                0
            };

            if (read_n == 0 and dead) {
                client.deinit(allocator);
                _ = clients.orderedRemove(i);
                continue;
            }

            if (read_n > 0) {
                try client.line_buf.appendSlice(tmp[0..read_n]);
            }

            while (true) {
                if (client.pending_bytes) |expected| {
                    const buf = client.line_buf.items;
                    if (buf.len < expected + 2) break;

                    const payload = buf[0..expected];
                    const crlf = buf[expected .. expected + 2];
                    if (!std.mem.eql(u8, crlf, "\r\n")) {
                        try send(client.socket, "-ERR 'invalid payload terminator'\r\n");
                        dead = true;
                        break;
                    }

                    const subject = client.pending_subject.?;
                    if (subscriptions.get(subject)) |subs| {
                        for (subs.items) |sub| {
                            if (sub.conn_index >= clients.items.len) continue;
                            var msg = std.ArrayList(u8).init(allocator);
                            defer msg.deinit();
                            try msg.writer().print("MSG {s} {s} {d}\r\n", .{ subject, sub.sid, payload.len });
                            try msg.appendSlice(payload);
                            try msg.appendSlice("\r\n");
                            _ = clients.items[sub.conn_index].socket.writeAll(msg.items) catch {};
                        }
                    }

                    allocator.free(subject);
                    if (client.pending_reply_to) |r| allocator.free(r);
                    client.pending_subject = null;
                    client.pending_reply_to = null;
                    client.pending_bytes = null;
                    _ = client.line_buf.replaceRange(0, expected + 2, "") catch {};
                    continue;
                }

                const maybe_idx = std.mem.indexOf(u8, client.line_buf.items, "\r\n");
                if (maybe_idx == null) break;
                const idx = maybe_idx.?;
                const line = client.line_buf.items[0..idx];
                const parts = splitSpaces(line);

                if (std.mem.eql(u8, parts[0], "PING")) {
                    try send(client.socket, "PONG\r\n");
                } else if (std.mem.eql(u8, parts[0], "CONNECT")) {
                    // ignore options for now
                } else if (std.mem.eql(u8, parts[0], "SUB")) {
                    const subject = try allocator.dupe(u8, parts[1]);
                    const sid = try allocator.dupe(u8, parts[2]);
                    if (!subscriptions.contains(subject)) {
                        try subscriptions.put(subject, std.ArrayList(Subscription).init(allocator));
                    } else {
                        allocator.free(subject);
                    }
                    var subs = subscriptions.getPtr(parts[1]).?;
                    try subs.append(.{ .conn_index = i, .sid = sid });
                } else if (std.mem.eql(u8, parts[0], "UNSUB")) {
                    const sid = parts[1];
                    var it = subscriptions.iterator();
                    while (it.next()) |entry| {
                        var j: usize = 0;
                        while (j < entry.value_ptr.items.len) {
                            const sub = entry.value_ptr.items[j];
                            if (std.mem.eql(u8, sub.sid, sid) and sub.conn_index == i) {
                                allocator.free(sub.sid);
                                _ = entry.value_ptr.orderedRemove(j);
                                continue;
                            }
                            j += 1;
                        }
                    }
                } else if (std.mem.eql(u8, parts[0], "PUB")) {
                    client.pending_subject = try allocator.dupe(u8, parts[1]);
                    const len_idx: usize = if (parts[3].len > 0) 3 else 2;
                    client.pending_bytes = try std.fmt.parseInt(usize, parts[len_idx], 10);
                    if (len_idx == 3) client.pending_reply_to = try allocator.dupe(u8, parts[2]);
                } else {
                    try send(client.socket, "-ERR 'unsupported command'\r\n");
                }

                _ = client.line_buf.replaceRange(0, idx + 2, "") catch {};
            }

            if (dead) {
                client.deinit(allocator);
                _ = clients.orderedRemove(i);
                continue;
            }
            i += 1;
        }

        std.time.sleep(2 * std.time.ns_per_ms);
    }
}
