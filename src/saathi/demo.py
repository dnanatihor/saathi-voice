"""Print one fixture dialog and the offline NLU metrics. `uv run saathi-demo`."""

from saathi.dialog.graph import DialogSession
from saathi.eval_report import nlu_metrics
from saathi.phrases import load_phrases


def main() -> None:
    phrases = load_phrases()
    session = DialogSession("medication_reminder", phrases)
    lines = [f"साथी: {line}" for line in session.start().spoken]
    reply = "हाँ, ले ली"
    lines.append(f"बाबूजी: {reply}")
    lines.extend(f"साथी: {line}" for line in session.user_turn(reply).spoken)
    metrics = nlu_metrics()
    print("\n".join(lines))
    print(f"intent accuracy: {metrics['intent_accuracy']:.2f}")
    print(f"emergency recall: {metrics['emergency_recall']:.2f}")


if __name__ == "__main__":
    main()
