interface SpeechRecognitionResultLike {
  readonly transcript: string;
}

interface SpeechRecognitionEvent extends Event {
  results: ArrayLike<ArrayLike<SpeechRecognitionResultLike>>;
}

interface SpeechListener {
  lang: string;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  start: () => void;
}

interface SpeechConstructor {
  new (): SpeechListener;
}

interface Window {
  __saathiUtter?: (text: string) => void;
  SpeechRecognition?: SpeechConstructor;
  webkitSpeechRecognition?: SpeechConstructor;
}
