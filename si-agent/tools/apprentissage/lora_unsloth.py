# -*- coding: utf-8 -*-
"""Adaptation LoRA du décideur des priorités (livraison #828, BACKLOG 132 T5) -- kit à lancer sur un hôte GPU NVIDIA.

  python3 -m venv ~/lora && . ~/lora/bin/activate && pip install unsloth
  # jeu « train » exporté depuis Parc IA > Apprentissage (ou curl .../apprentissage/jeu?format=jsonl&part=train)
  python3 lora_unsloth.py --jeu decideur-train.jsonl --base unsloth/Qwen3-4B-Instruct-2507 --sortie ~/decideur-lora-1
  ollama create decideur-lora:1 -f ~/decideur-lora-1/Modelfile
puis Parc IA > Apprentissage : renseigner le modèle produit et « Évaluer » (part test, décisions humaines) ; ne le
déclarer pour l'usage « décideur » (Usages) que s'il fait mieux que le modèle de production. Non exécuté à la livraison.
Les données (nos décisions) restent sur l'hôte : pas d'envoi, pas de compte externe."""
import argparse
import json
import os


def main():
    ap = argparse.ArgumentParser(description="LoRA du décideur (Unsloth) -> GGUF -> Ollama")
    ap.add_argument("--jeu", required=True, help="JSONL {messages: [...]} exporté par le hub (part train)")
    ap.add_argument("--base", default="unsloth/Qwen3-4B-Instruct-2507")
    ap.add_argument("--sortie", required=True)
    ap.add_argument("--rang", type=int, default=16)
    ap.add_argument("--epoques", type=float, default=2.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--contexte", type=int, default=4096)
    ap.add_argument("--quantif", default="q4_k_m")
    a = ap.parse_args()

    from datasets import load_dataset
    from trl import SFTConfig, SFTTrainer
    from unsloth import FastLanguageModel

    model, tok = FastLanguageModel.from_pretrained(model_name=a.base, max_seq_length=a.contexte, load_in_4bit=True)
    model = FastLanguageModel.get_peft_model(model, r=a.rang, lora_alpha=a.rang, lora_dropout=0, bias="none",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
                                             use_gradient_checkpointing="unsloth", random_state=3407)
    ds = load_dataset("json", data_files=a.jeu)["train"]
    ds = ds.map(lambda e: {"text": tok.apply_chat_template(e["messages"], tokenize=False)})
    print("exemples : %d" % len(ds))
    tr = SFTTrainer(model=model, tokenizer=tok, train_dataset=ds,
                    args=SFTConfig(dataset_text_field="text", per_device_train_batch_size=2, gradient_accumulation_steps=4,
                                   num_train_epochs=a.epoques, learning_rate=a.lr, warmup_ratio=0.05, logging_steps=5,
                                   output_dir=os.path.join(a.sortie, "points"), seed=3407, report_to="none"))
    stats = tr.train()
    os.makedirs(a.sortie, exist_ok=True)
    model.save_pretrained_gguf(a.sortie, tok, quantization_method=a.quantif)
    gguf = sorted(f for f in os.listdir(a.sortie) if f.endswith(".gguf"))[-1]
    with open(os.path.join(a.sortie, "Modelfile"), "w") as fh:
        fh.write("FROM ./%s\nPARAMETER temperature 0\n" % gguf)
    with open(os.path.join(a.sortie, "entrainement.json"), "w") as fh:
        json.dump({"base": a.base, "jeu": os.path.abspath(a.jeu), "exemples": len(ds), "rang": a.rang, "epoques": a.epoques, "lr": a.lr,
                   "perte_finale": getattr(stats, "training_loss", None), "gguf": gguf}, fh, indent=1)
    print("GGUF : %s ; Modelfile prêt : ollama create <nom> -f %s" % (gguf, os.path.join(a.sortie, "Modelfile")))


if __name__ == "__main__":
    main()
