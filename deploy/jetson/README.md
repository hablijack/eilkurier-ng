# Sprachmodell auf dem Jetson (llama.cpp)

Eilkurier spricht mit dem Jetson Orin Nano Super (8 GB, JetPack 7.2.1, CUDA 13.2) über die OpenAI-kompatible API
von `llama-server`. Ein Port (8080), zwei Modelle im Router-Modus. Welches Modell eine Anfrage bekommt, entscheidet
das Feld `model`:

| Modell (`model`) | Datei | Läuft auf | Zweck |
|---|---|---|---|
| `qwen3.5-9b` | `Qwen3.5-9B-IQ4_XS.gguf` (unsloth, 5,2 GB) | GPU, 4096 Token Kontext, Denkmodus aus | Meldungen schreiben, Geschichten zuordnen |
| `embeddinggemma` | `embeddinggemma-300M-Q8_0.gguf` (ggml-org, 0,3 GB) | CPU, 512 Token | Embeddings für „Was bisher geschah“ |

In Eilkurier (`.env`): `EILKURIER_LLM_URL=http://jetson.fritz.box:8080`, `EILKURIER_LLM_MODEL=qwen3.5-9b`,
`EILKURIER_EMBEDDING_MODEL=embeddinggemma`, `EILKURIER_LLM_EXTRA_BODY` leer.

## Dateien

Auf dem Jetson liegt alles unter `/ssd/llama.cpp` (Kopien hier im Repo):

- `compose.yaml`: der Dienst (`restart: unless-stopped`, startet nach einem Reboot von selbst)
- `models.ini`: die Modell-Presets für den Router
- `Dockerfile.jetson`: entfernt die CUDA-Kompatibilitätsbibliotheken aus dem `nvidia/cuda`-Image
- `models/`: die GGUF-Dateien, `src/`: llama.cpp-Quellen (Tag `v1.0.0`)

## Neu aufsetzen

```bash
cd /ssd/llama.cpp
git clone --depth 1 --branch v1.0.0 https://github.com/ggml-org/llama.cpp src
(cd src && docker build -f .devops/cuda.Dockerfile --target server \
  --build-arg CUDA_VERSION=13.2.1 --build-arg CUDA_DOCKER_ARCH=87 -t llama.cpp-server:v1.0.0-cu132 .)  # ~30 min
docker build -f Dockerfile.jetson -t llama.cpp-server:v1.0.0-cu132-jetson .
curl -L -o models/Qwen3.5-9B-IQ4_XS.gguf \
  https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-IQ4_XS.gguf
curl -L -o models/embeddinggemma-300M-Q8_0.gguf \
  https://huggingface.co/ggml-org/embeddinggemma-300M-GGUF/resolve/main/embeddinggemma-300M-Q8_0.gguf
docker compose -f compose.yaml up -d
curl -s localhost:8080/v1/models   # beide Modelle mit status "loaded"
```

## Stolpersteine (JetPack 7.2)

- **Ollama** fällt unter JetPack 7.2 auf die CPU zurück. Alte `dustynv`-Container (CUDA 12.6) laufen nicht mehr.
  Das offizielle `nvidia/cuda:13.2.1`-Image (arm64/SBSA) funktioniert.
- **Container startet nicht** (`nvidia-cdi-hook cudacompat … slice bounds out of range`): Der NVIDIA Container
  Toolkit 1.19.1 stürzt an `/usr/local/cuda-13.2/compat_orin/libcuda.so*` ab. Deshalb gibt es
  `Dockerfile.jetson`. Die Bibliotheken braucht niemand, der Host-Treiber kann CUDA 13.2 bereits.
- **Speicher:** CPU und GPU teilen sich die 8 GB. `llama-server` v1.0.0 hält ohne `cache-ram = 0` bis zu 8 GB
  Prompt-Cache im RAM. Nach rund 15 Artikeln lagert der Jetson dann aus. Ein zweiter CUDA-Kontext für die
  Embeddings kostet ~0,6 GB, deshalb laufen sie auf der CPU (`device = none`, `load-mode = mmap`, `no-repack`).
- **Nur ein großer Dienst passt:** guitar-vision (pausiert seit 2026-11-18) und dieser Dienst passen nicht
  gleichzeitig in den Speicher. Vor dem Start des einen den anderen stoppen.
- Vom Mac aus `jetson.fritz.box` statt `jetson.local` verwenden: mDNS-Auflösung in Python kostet pro neuer
  Verbindung Sekunden bis Minuten, und der Router schließt die Verbindung nach jeder Antwort.

## Messwerte (2026-11-18, 15 echte Artikel, `enrich`-Prompt)

| Modell | gültig | s/Artikel (Median) | Token/s | RAM gesamt (Spitze) |
|---|---|---|---|---|
| Gemma 3 4B Q6_K | 14/15 | 15 | 16 | 4,9 GB |
| Qwen3.5-4B Q6_K | 14/15 | 19 | 14 | 5,1 GB |
| **Qwen3.5-9B IQ4_XS** (gewählt) | 15/15 | 23 | 13 | 6,3 GB (mit Embeddings 6,5 GB) |
| Qwen3.5-9B Q4_K_M | 15/15 | 27 | 11 | 6,7 GB (kein Platz für Embeddings) |

Qwen3.5-9B übernahm Zahlen und Namen am genauesten und unterscheidet die Wichtigkeit (Gemma gab fast immer 3).
Bekannte Schwäche: Gelegentlich ordnet es eine Aussage der falschen Person zu. Die Zahlenprüfung in
`validate_enrichment` fängt das nicht ab.
