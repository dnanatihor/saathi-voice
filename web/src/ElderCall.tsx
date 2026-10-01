import { useState } from "react";

type Reply = {
  spoken: string[];
  audio_b64: string;
  latency_s?: number;
  states: string[];
};

function socketUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/voice`;
}

function play(audioB64: string) {
  const audio = new Audio(`data:audio/wav;base64,${audioB64}`);
  void audio.play().catch(() => undefined);
}

export function ElderCall() {
  const [lines, setLines] = useState<string[]>([]);
  const [latency, setLatency] = useState<number | null>(null);

  function talk() {
    const socket = new WebSocket(socketUrl());
    socket.onmessage = (event: MessageEvent<string>) => {
      const reply = JSON.parse(event.data) as Reply;
      setLines((current) => [...current, ...reply.spoken]);
      if (typeof reply.latency_s === "number") {
        setLatency(reply.latency_s);
      }
      if (reply.audio_b64) {
        play(reply.audio_b64);
      }
    };
    window.__saathiUtter = (text: string) => {
      socket.send(new TextEncoder().encode(text));
      socket.send(JSON.stringify({ type: "end" }));
    };
    const recognition = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (recognition) {
      const listener = new recognition();
      listener.lang = "hi-IN";
      listener.onresult = (event: SpeechRecognitionEvent) => {
        const text = event.results[0]?.[0]?.transcript ?? "";
        window.__saathiUtter?.(text);
      };
      socket.onopen = () => listener.start();
    }
  }

  return (
    <main>
      <button type="button" onClick={talk} style={{ fontSize: "2rem", minHeight: "8rem", width: "100%" }}>
        बात करें
      </button>
      <section aria-label="Conversation">
        {lines.map((line, index) => (
          <p key={`${index}-${line}`}>{line}</p>
        ))}
      </section>
      {latency !== null ? <p>latency {latency.toFixed(3)} s</p> : null}
    </main>
  );
}
