import http from "k6/http";
import { check } from "k6";

export default function () {
  const payload = JSON.stringify({
    fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    mode: "blitz",
    movetime_ms: 80,
  });

  const res = http.post("http://host.docker.internal:8000/move", payload, {
    headers: { "Content-Type": "application/json" },
  });

  check(res, { "status is 200": (r) => r.status === 200 });
}
