/** End of speech when the level stays under the threshold after speech has started. */

const FRAME_MS = 100;
const DEFAULT_SILENCE_MS = 6000;
const SPEECH_THRESHOLD = 0.02;

export function speechShouldEnd(
  levels: number[],
  silenceMs = DEFAULT_SILENCE_MS,
  threshold = SPEECH_THRESHOLD,
): boolean {
  let heard = false;
  let silentMs = 0;
  for (const level of levels) {
    if (level >= threshold) {
      heard = true;
      silentMs = 0;
    } else if (heard) {
      silentMs += FRAME_MS;
    }
  }
  return heard && silentMs >= silenceMs;
}
