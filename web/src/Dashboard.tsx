import { useState } from "react";
import { AdherenceGrid, type AdherenceCell } from "./AdherenceGrid";

export function spokenPreview(honorific: string, spokenLabel: string) {
  return `${honorific}, ${spokenLabel} का समय है।`;
}

export function Dashboard({ cells }: { cells: AdherenceCell[] }) {
  const [label, setLabel] = useState("बीपी की दवा");
  const [honorific, setHonorific] = useState("बाबूजी");
  return (
    <main>
      <h1>Saathi</h1>
      <form aria-label="Login">
        <label>
          Email
          <input name="login" type="email" autoComplete="username" />
        </label>
        <label>
          Password
          <input name="password" type="password" autoComplete="current-password" />
        </label>
        <button type="button">Log in</button>
      </form>
      <section aria-label="Elder">
        <h2>Elder</h2>
        <label>
          Honorific
          <input value={honorific} onChange={(event) => setHonorific(event.target.value)} />
        </label>
      </section>
      <section aria-label="Medication">
        <h2>Medication</h2>
        <label>
          Spoken label
          <input value={label} onChange={(event) => setLabel(event.target.value)} />
        </label>
        <p>Preview: {spokenPreview(honorific, label)}</p>
        <p>Audio preview starts when a speech provider is configured.</p>
      </section>
      <section aria-label="Contacts">
        <h2>Contacts</h2>
      </section>
      <section aria-label="Consent">
        <h2>Consent</h2>
        <label>
          <input type="checkbox" /> Reminders
        </label>
      </section>
      <AdherenceGrid cells={cells} />
      <section aria-label="Timeline">
        <h2>Timeline</h2>
      </section>
      <section aria-label="Check-ins">
        <h2>Check-ins</h2>
      </section>
      <section aria-label="Simulate call">
        <h2>Simulate a call</h2>
        <textarea aria-label="Elder reply" />
      </section>
      <button type="button">Export data</button>
      <button type="button">Erase elder data</button>
    </main>
  );
}
