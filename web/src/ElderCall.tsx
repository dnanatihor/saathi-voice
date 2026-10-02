import { useState, type FormEvent } from "react";

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

async function playThrough(context: AudioContext, audioB64: string) {
  const binary = atob(audioB64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const copy = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  const buffer = await context.decodeAudioData(copy);
  const source = context.createBufferSource();
  source.buffer = buffer;
  source.connect(context.destination);
  source.start();
}

export function ElderCall() {
  const [lines, setLines] = useState<string[]>([]);
  const [answer, setAnswer] = useState("");
  const [latency, setLatency] = useState<number | null>(null);
  const [status, setStatus] = useState("Press the button. Words appear under it.");

  function talk() {
    const context = new AudioContext();
    void context.resume();
    setStatus("Connecting…");
    const socket = new WebSocket(socketUrl());
    socket.onmessage = (event: MessageEvent<string>) => {
      const reply = JSON.parse(event.data) as Reply;
      if (reply.spoken.length > 0) {
        setLines((current) => [...current, ...reply.spoken]);
        setStatus(reply.states.includes("Close") ? "Call finished." : "Type your reply below, or speak.");
      }
      if (typeof reply.latency_s === "number") {
        setLatency(reply.latency_s);
      }
      if (reply.audio_b64) {
        void playThrough(context, reply.audio_b64).catch(() => undefined);
      }
    };
    socket.onerror = () => setStatus("Could not connect. Is the page http://127.0.0.1:8010/ ?");
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
      socket.addEventListener("message", () => listener.start(), { once: true });
    }
  }

  function sendAnswer(event: FormEvent) {
    event.preventDefault();
    const text = answer.trim();
    if (!text || !window.__saathiUtter) {
      setStatus("Press बात करें first.");
      return;
    }
    setLines((current) => [...current, text]);
    window.__saathiUtter(text);
    setAnswer("");
  }

  return (
    <main>
      <button type="button" onClick={talk} style={{ fontSize: "2rem", minHeight: "8rem", width: "100%" }}>
        बात करें
      </button>
      <p style={{ fontSize: "1.25rem" }}>{status}</p>
      <section aria-label="Conversation" style={{ fontSize: "1.5rem" }}>
        {lines.map((line, index) => (
          <p key={`${index}-${line}`}>{line}</p>
        ))}
      </section>
      <form onSubmit={sendAnswer}>
        <label>
          Your reply
          <input
            aria-label="Your reply"
            value={answer}
            placeholder="हाँ, ले ली"
            onChange={(event) => setAnswer(event.target.value)}
          />
        </label>
        <button type="submit">Send</button>
      </form>
      {latency !== null ? <p>latency {latency.toFixed(3)} s</p> : null}
    </main>
  );
}
