from pathlib import Path
from typing import List
import uuid
import modal
import os
import boto3
import time

from pydantic import BaseModel, ValidationError
import requests

try:
    from .modal_app import app
    from .modal_demucs_server import DemucsServer, separate_stems  # noqa: F401
    from .modal_faceswap_server import FaceSwapServer, face_swap  # noqa: F401
except ImportError:  # Modal executes the file from its source directory.
    from modal_app import app
    from modal_demucs_server import DemucsServer, separate_stems  # noqa: F401
    from modal_faceswap_server import FaceSwapServer, face_swap  # noqa: F401
from prompts import LYRICS_GENERATOR_PROMPT, PROMPT_GENERATOR_PROMPT

image = (
    modal.Image.debian_slim()
    .apt_install("git", "ffmpeg")
    .run_commands([
        "git clone https://github.com/ace-step/ACE-Step.git /tmp/ACE-Step",
        "cd /tmp/ACE-Step && git checkout --detach 1bee4c9f5b43e30995f8d4d33b3919197ce1bd68",
        "cd /tmp/ACE-Step && pip install .",
    ])
    .pip_install(
        "transformers==4.50.0",
        "accelerate==1.6.0",
        "diffusers==0.33.0",
        "fastapi[standard]",
        "boto3",
        "pydantic",
        "requests",
        "torch==2.8.0",
        "torchaudio==2.8.0",
        "torchcodec==0.7.0",
    )
    .env({"HF_HOME": "/.cache/huggingface"})
    .add_local_python_source(
        "modal_demucs_server",
        "modal_faceswap_server",
        "prompts",
    )
    .add_local_file(
        str(Path(__file__).with_name("modal_app.py")),
        remote_path="/root/modal_app.py",
    )
)

controller_image = (
    modal.Image.debian_slim()
    .pip_install("fastapi[standard]", "boto3", "pydantic", "requests")
    .add_local_python_source(
        "modal_demucs_server",
        "modal_faceswap_server",
        "prompts",
    )
    .add_local_file(
        str(Path(__file__).with_name("modal_app.py")),
        remote_path="/root/modal_app.py",
    )
)

model_volume = modal.Volume.from_name("ace-step-models", create_if_missing=True)
hf_volume = modal.Volume.from_name("qwen-hf-cache", create_if_missing=True)


@app.function(
    image=image,
    volumes={"/models": model_volume, "/.cache/huggingface": hf_volume},
    timeout=1800,
)
def prepare_model_volumes():
    """Descarga una vez los modelos y persiste sus caches en Modal Volumes."""
    from huggingface_hub import snapshot_download

    snapshot_download(
        "ACE-Step/ACE-Step-v1-3.5B",
        cache_dir="/models",
    )
    snapshot_download(
        "Qwen/Qwen2-7B-Instruct",
        cache_dir="/.cache/huggingface",
    )
    snapshot_download(
        "stabilityai/sdxl-turbo",
        cache_dir="/.cache/huggingface",
    )

    model_volume.commit()
    hf_volume.commit()
    return {"status": "ready"}

music_gen_secrets = modal.Secret.from_name("music-gen-secret")


def _get_r2_storage():
    """Crea el cliente R2 y devuelve también el bucket configurado."""
    required = (
        "R2_ENDPOINT",
        "R2_REGION",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_DOCUMENTS_BUCKET",
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Faltan variables R2 en el secreto de Modal: "
            + ", ".join(missing)
        )

    client = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        region_name=os.environ["R2_REGION"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    return client, os.environ["R2_DOCUMENTS_BUCKET"]


class AudioGenerationBase(BaseModel):
    audio_duration: float = 180.0
    seed: int = -1
    guidance_scale: float = 10.0
    infer_step: int = 100
    instrumental: bool = False
    vocal_type: str = 'auto'   # 'male' | 'female' | 'auto'
    language: str = 'es'       # 'es' | 'en'
    client_job_id: str | None = None


class GenerateFromDescriptionRequest(AudioGenerationBase):
    full_described_song: str


class GenerateWithCustomLyricsRequest(AudioGenerationBase):
    prompt: str
    lyrics: str


class GenerateWithDescribedLyricsRequest(AudioGenerationBase):
    prompt: str
    described_lyrics: str


class GenerateMusicResponseS3(BaseModel):
    s3_key: str
    cover_image_s3_key: str
    categories: List[str]
    lyrics: str = ""  # letra generada o provista, para guardarla en Django


music_job_status = modal.Dict.from_name(
    "gm-music-job-status", create_if_missing=True
)
MUSIC_JOB_TTL_SECONDS = 24 * 60 * 60
MUSIC_STATUS_LOCK_SECONDS = 30
MUSIC_STATUS_LOCK_WAIT_SECONDS = 2


def _music_set_status(job_id: str, **values):
    lock_key = f"status-update:{job_id}"
    lock_id = str(uuid.uuid4())
    deadline = time.time() + MUSIC_STATUS_LOCK_WAIT_SECONDS

    while time.time() < deadline:
        existing_lock = music_job_status.get(lock_key)
        if isinstance(existing_lock, dict) and existing_lock.get("expires_at", 0) <= int(time.time()):
            reclaim_key = f"status-reclaim:{job_id}"
            if music_job_status.put(
                reclaim_key,
                {"created_at": int(time.time()), "expires_at": int(time.time()) + MUSIC_STATUS_LOCK_SECONDS},
                skip_if_exists=True,
            ):
                try:
                    latest_lock = music_job_status.get(lock_key)
                    if isinstance(latest_lock, dict) and latest_lock.get("expires_at", 0) <= int(time.time()):
                        music_job_status.pop(lock_key, None)
                finally:
                    music_job_status.pop(reclaim_key, None)

        if music_job_status.put(
            lock_key,
            {
                "lock_id": lock_id,
                "created_at": int(time.time()),
                "expires_at": int(time.time()) + MUSIC_STATUS_LOCK_SECONDS,
            },
            skip_if_exists=True,
        ):
            break
        time.sleep(0.05)
    else:
        raise RuntimeError(f"No se pudo actualizar el estado del job {job_id}: lock ocupado.")

    try:
        current = music_job_status.get(job_id, {})
        current.update(values)
        current['updated_at'] = int(time.time())
        music_job_status[job_id] = current
    finally:
        current_lock = music_job_status.get(lock_key)
        if isinstance(current_lock, dict) and current_lock.get("lock_id") == lock_id:
            music_job_status.pop(lock_key, None)


def _music_status(job_id: str):
    value = music_job_status.get(job_id)
    if not value:
        return None
    if value.get('expires_at', 0) <= int(time.time()):
        music_job_status.pop(job_id, None)
        client_job_id = value.get('client_job_id')
        if client_job_id:
            music_job_status.pop(f'client:{client_job_id}', None)
        return None
    return value


def _claim_music_job(client_job_id: str | None) -> str:
    if client_job_id:
        client_key = f'client:{client_job_id}'
        existing = music_job_status.get(client_key)
        existing_id = existing.get('job_id') if isinstance(existing, dict) else existing
        if existing_id and _music_status(existing_id):
            return existing_id
        if existing:
            music_job_status.pop(client_key, None)

        job_id = str(uuid.uuid4())
        claimed = music_job_status.put(
            client_key,
            {'job_id': job_id, 'expires_at': int(time.time()) + MUSIC_JOB_TTL_SECONDS},
            skip_if_exists=True,
        )
        if not claimed:
            existing = music_job_status.get(client_key)
            existing_id = existing.get('job_id') if isinstance(existing, dict) else existing
            if existing_id:
                return existing_id
            raise RuntimeError('No se pudo reclamar el job musical.')
    else:
        job_id = str(uuid.uuid4())

    music_job_status[job_id] = {
        'status': 'queued',
        'progress_pct': 0,
        'result': None,
        'error_message': None,
        'client_job_id': client_job_id,
        'expires_at': int(time.time()) + MUSIC_JOB_TTL_SECONDS,
    }
    return job_id


def _model_volumes_ready() -> bool:
    required_paths = (
        Path("/models/hub/models--ACE-Step--ACE-Step-v1-3.5B"),
        Path("/.cache/huggingface/hub/models--Qwen--Qwen2-7B-Instruct"),
        Path("/.cache/huggingface/hub/models--stabilityai--sdxl-turbo"),
    )
    return all(path.exists() for path in required_paths)


def _spawn_music_job(request: dict, job_id: str):
    current = _music_status(job_id)
    if current and current.get('status') in {'processing', 'completed'}:
        return current

    spawn_key = f'spawn:{job_id}'
    lease_id = str(uuid.uuid4())
    claimed = music_job_status.put(
        spawn_key,
        {'lease_id': lease_id, 'expires_at': int(time.time()) + 300},
        skip_if_exists=True,
    )
    if not claimed:
        return _music_status(job_id) or current

    try:
        _music_set_status(job_id, status='queued', progress_pct=0, error_message=None)
        MusicGenServer().process.spawn(request, job_id, lease_id)
    except Exception as exc:
        music_job_status.pop(spawn_key, None)
        _music_set_status(job_id, status='failed', error_message=str(exc)[:500])
        raise
    return _music_status(job_id) or current


# ─── CAMBIO 1: scaledown_window aumentado a 300s (5 min) ───────────────────────
# Con 15s, la GPU se apagaba y re-encendía constantemente entre peticiones.
# Cada cold start de A100 tarda ~3-5 min y cuesta créditos. Con 300s, si llegan
# 2 requests en menos de 5 minutos, la GPU ya está caliente y no hay cold start.
# Ajustá este valor según tu volumen de tráfico real.
@app.cls(
    image=image,
    gpu="A100",
    volumes={"/models": model_volume, "/.cache/huggingface": hf_volume},
    secrets=[music_gen_secrets],
    timeout=1800,
    scaledown_window=300,
)
class MusicGenServer:

    @modal.enter()
    def load_model(self):
        import torch
        from acestep.pipeline_ace_step import ACEStepPipeline
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from diffusers import AutoPipelineForText2Image

        if not _model_volumes_ready():
            raise RuntimeError(
                "Los volúmenes de modelos no están preparados. "
                "Ejecuta `modal run ml/modal_music_server.py::prepare_model_volumes`."
            )

        # ── Music Generation Model ──────────────────────────────────────────────
        # CAMBIO 2: cpu_offload=True
        # ACE-Step es el modelo más pesado. Con cpu_offload=True, las capas que
        # no se usan en ese momento se mueven a RAM, liberando VRAM para Qwen y SDXL.
        # Si tu A100 tiene 80GB podés volver a False, pero con 40GB es necesario.
        self.music_model = ACEStepPipeline(
            checkpoint_dir="/models",
            dtype="bfloat16",
            torch_compile=False,
            cpu_offload=True,   # <-- CAMBIO: False → True
            overlapped_decode=False
        )

        # ── LLM (Qwen) ─────────────────────────────────────────────────────────
        model_id = "Qwen/Qwen2-7B-Instruct"
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.llm_model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype="auto",
            device_map="auto",
            cache_dir="/.cache/huggingface"
        )

        # ── Stable Diffusion (thumbnails) ───────────────────────────────────────
        self.image_pipe = AutoPipelineForText2Image.from_pretrained(
            "stabilityai/sdxl-turbo",
            torch_dtype=torch.float16,
            variant="fp16",
            cache_dir="/.cache/huggingface"
        )
        self.image_pipe.to("cuda")

    @modal.method()
    def process(self, request: dict, job_id: str, lease_id: str):
        worker_key = f"worker:{job_id}"
        claimed = music_job_status.put(
            worker_key,
            {
                "lease_id": lease_id,
                "expires_at": int(time.time()) + MUSIC_JOB_TTL_SECONDS,
            },
            skip_if_exists=True,
        )
        if not claimed:
            return

        try:
            _music_set_status(job_id, status="processing", progress_pct=10)
            mode = request["mode"]
            if mode == "from_description":
                parsed = GenerateFromDescriptionRequest(**request)
                result = self._generate_from_description(parsed)
            elif mode == "with_lyrics":
                parsed = GenerateWithCustomLyricsRequest(**request)
                result = self._generate_with_lyrics(parsed)
            elif mode == "with_described_lyrics":
                parsed = GenerateWithDescribedLyricsRequest(**request)
                result = self._generate_with_described_lyrics(parsed)
            else:
                raise ValueError(f"Modo desconocido: {mode}")

            payload = result.model_dump()
            _music_set_status(
                job_id,
                status="completed",
                progress_pct=100,
                result=payload,
                error_message=None,
            )
        except Exception as exc:
            _music_set_status(
                job_id,
                status="failed",
                progress_pct=0,
                error_message=str(exc)[:500],
            )
            raise
        finally:
            current_worker = music_job_status.get(worker_key)
            if (
                isinstance(current_worker, dict)
                and current_worker.get("lease_id") == lease_id
            ):
                music_job_status.pop(worker_key, None)
            spawn_key = f"spawn:{job_id}"
            current_spawn = music_job_status.get(spawn_key)
            if (
                isinstance(current_spawn, dict)
                and current_spawn.get("lease_id") == lease_id
            ):
                music_job_status.pop(spawn_key, None)

    # ─── CAMBIO 3: helper centralizado de limpieza de memoria ──────────────────
    # En el código original, el gc.collect()+empty_cache() solo estaba en
    # generate_with_described_lyrics. Ahora se llama desde todos los flujos que
    # usan Qwen antes de pasarle el trabajo a ACE-Step.
    def _flush_llm_cache(self):
        import torch  # ← acá adentro
        import gc 
        """Libera la VRAM que ocupó Qwen antes de correr ACE-Step o SDXL."""
        gc.collect()
        torch.cuda.empty_cache()

    def prompt_qwen(self, question: str):
        messages = [{"role": "user", "content": question}]
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.llm_model.device)

        generated_ids = self.llm_model.generate(
            model_inputs.input_ids,
            max_new_tokens=512
        )
        generated_ids = [
            output_ids[len(input_ids):]
            for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        return self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

    # ── Mapas de tags por idioma y tipo de voz ───────────────────────────────
    _LANG_TAGS = {
        'en': 'English vocals, English lyrics',
        'es': 'Spanish vocals, Spanish lyrics',
        'fr': 'French vocals, French lyrics',
        'pt': 'Portuguese vocals, Portuguese lyrics',
        'de': 'German vocals, German lyrics',
        'it': 'Italian vocals, Italian lyrics',
    }
    _LANG_INSTRUCTIONS = {
        'es': 'Spanish (castellano)',
        'en': 'English',
        'fr': 'French (français)',
        'pt': 'Portuguese (português)',
        'de': 'German (Deutsch)',
        'it': 'Italian (italiano)',
        'auto': 'the same language as the description',
    }
    # Tags de voz más completos para que ACE-Step los reconozca con seguridad
    _VOCAL_TAGS = {
        'female': 'female vocal, female singer',
        'male':   'male vocal, male singer',
    }

    def _resolve_language(self, language: str, text: str = '') -> str:
        """Detecta español por heurística de tildes si language='auto', sin llamar a Qwen."""
        if language != 'auto':
            return language
        import re
        if re.search(r'[áéíóúüñÁÉÍÓÚÜÑ¿¡]', text):
            return 'es'
        return 'en'

    def _inject_vocal_type(self, prompt: str, vocal_type: str) -> str:
        """Fuerza el tipo de voz en el prompt, eliminando siempre el tag contrario."""
        if vocal_type not in self._VOCAL_TAGS:
            return prompt
        tag      = self._VOCAL_TAGS[vocal_type]           # "female vocal, female singer"
        opposite = self._VOCAL_TAGS['male' if vocal_type == 'female' else 'female']

        # Eliminar TODOS los tags del tipo contrario
        parts = [t.strip() for t in prompt.split(',')]
        cleaned = [p for p in parts if p and not any(o.lower() in p.lower() for o in opposite.split(','))]

        # Añadir nuestros tags si no están ya
        for t in tag.split(','):
            t = t.strip()
            if t.lower() not in ' '.join(cleaned).lower():
                cleaned.insert(0, t)

        return ', '.join(cleaned)

    def _inject_language(self, prompt: str, resolved_lang: str) -> str:
        """Inyecta los tags de idioma en el prompt, evitando duplicados."""
        lang_tag = self._LANG_TAGS.get(resolved_lang, '')
        if not lang_tag:
            return prompt
        first_tag = lang_tag.split(',')[0].strip().lower()
        if first_tag in prompt.lower():
            return prompt
        return f"{lang_tag}, {prompt}"

    def generate_prompt(self, description: str) -> str:
        full_prompt = PROMPT_GENERATOR_PROMPT.format(user_prompt=description)
        return self.prompt_qwen(full_prompt)

    def generate_lyrics(self, description: str, duration: float, language: str = 'en') -> str:
        lang_instruction = self._LANG_INSTRUCTIONS.get(language, 'the same language as the description')
        full_prompt = LYRICS_GENERATOR_PROMPT.format(
            description=description,
            duration=duration,
            language_instruction=lang_instruction,
        )
        return self.prompt_qwen(full_prompt)

    def generate_categories(self, description: str) -> List[str]:
        prompt = (
            f"Based on the following music description, list 3-5 relevant genres or categories "
            f"as a comma-separated list. For example: Pop, Electronic, Sad, 80s. "
            f"Description: '{description}'"
        )
        response_text = self.prompt_qwen(prompt)
        return [cat.strip() for cat in response_text.split(",") if cat.strip()]

    def generate_and_upload_to_s3(
        self,
        prompt: str,
        lyrics: str,
        instrumental: bool,
        audio_duration: float,
        infer_step: int,
        guidance_scale: float,
        seed: int,
        description_for_categorization: str,
        vocal_type: str = 'auto',
        language: str = 'auto',
    ) -> GenerateMusicResponseS3:
        resolved_lang = self._resolve_language(language, description_for_categorization)
        prompt = self._inject_vocal_type(prompt, vocal_type)
        prompt = self._inject_language(prompt, resolved_lang)
        final_lyrics = "[instrumental]" if instrumental else lyrics
        print(f"Prompt: {prompt}")
        print(f"Lyrics: {final_lyrics[:120]}...")

        r2_client, bucket_name = _get_r2_storage()
        uploaded_keys = []
        output_dir = "/tmp/outputs"
        os.makedirs(output_dir, exist_ok=True)

        try:
            # ── 1. Generar audio con ACE-Step ───────────────────────────────────
            output_path = os.path.join(output_dir, f"{uuid.uuid4()}.wav")
            self.music_model(
                prompt=prompt,
                lyrics=final_lyrics,
                audio_duration=audio_duration,
                infer_step=infer_step,
                guidance_scale=guidance_scale,
                save_path=output_path,
                manual_seeds=str(seed),
            )
            audio_s3_key = f"{uuid.uuid4()}.wav"
            r2_client.upload_file(output_path, bucket_name, audio_s3_key)
            uploaded_keys.append(audio_s3_key)
            os.remove(output_path)

            # ── 2. Generar thumbnail con SDXL ───────────────────────────────────
            thumbnail_prompt = f"{prompt}, album cover art"
            image = self.image_pipe(
                prompt=thumbnail_prompt, num_inference_steps=2, guidance_scale=0.0
            ).images[0]
            image_output_path = os.path.join(output_dir, f"{uuid.uuid4()}.png")
            image.save(image_output_path)
            image_s3_key = f"{uuid.uuid4()}.png"
            r2_client.upload_file(image_output_path, bucket_name, image_s3_key)
            uploaded_keys.append(image_s3_key)
            os.remove(image_output_path)

            # ── 3. Generar categorías con Qwen ──────────────────────────────────
            categories = self.generate_categories(description_for_categorization)

            return GenerateMusicResponseS3(
                s3_key=audio_s3_key,
                cover_image_s3_key=image_s3_key,
                categories=categories,
                lyrics=final_lyrics if final_lyrics != "[instrumental]" else "",
            )
        except Exception:
            for key in uploaded_keys:
                try:
                    r2_client.delete_object(Bucket=bucket_name, Key=key)
                except Exception:
                    pass
            raise

    # ─── CAMBIO 5: endpoint `generate` de prueba ELIMINADO ─────────────────────
    # El endpoint hardcodeado /generate existía solo para testing pero estaba
    # expuesto en producción. Cualquier llamada accidental (o un bot que lo
    # descubra) consumía una generación completa de 180s en A100. Eliminado.

    def _generate_from_description(self, request: GenerateFromDescriptionRequest) -> GenerateMusicResponseS3:
        resolved_lang = self._resolve_language(request.language, request.full_described_song)
        prompt = self.generate_prompt(request.full_described_song)
        lyrics = ""
        if not request.instrumental:
            lyrics = self.generate_lyrics(request.full_described_song, request.audio_duration, resolved_lang)

        self._flush_llm_cache()

        return self.generate_and_upload_to_s3(
            prompt=prompt,
            lyrics=lyrics,
            vocal_type=request.vocal_type,
            language=resolved_lang,
            description_for_categorization=request.full_described_song,
            **request.model_dump(exclude={"full_described_song", "vocal_type", "language", "client_job_id"}),
        )

    def _generate_with_lyrics(self, request: GenerateWithCustomLyricsRequest) -> GenerateMusicResponseS3:
        resolved_lang = self._resolve_language(request.language, request.lyrics)
        return self.generate_and_upload_to_s3(
            prompt=request.prompt,
            lyrics=request.lyrics,
            vocal_type=request.vocal_type,
            language=resolved_lang,
            description_for_categorization=request.prompt,
            **request.model_dump(exclude={"prompt", "lyrics", "vocal_type", "language", "client_job_id"}),
        )

    def _generate_with_described_lyrics(self, request: GenerateWithDescribedLyricsRequest) -> GenerateMusicResponseS3:
        resolved_lang = self._resolve_language(request.language, request.described_lyrics)
        lyrics = ""
        if not request.instrumental:
            lyrics = self.generate_lyrics(request.described_lyrics, request.audio_duration, resolved_lang)

        self._flush_llm_cache()

        return self.generate_and_upload_to_s3(
            prompt=request.prompt,
            lyrics=lyrics,
            vocal_type=request.vocal_type,
            language=resolved_lang,
            description_for_categorization=request.prompt,
            **request.model_dump(exclude={"described_lyrics", "prompt", "vocal_type", "language", "client_job_id"}),
        )

def _music_controller(request: dict, mode: str):
    if request.get("action") == "status":
        job_id = request.get("remote_job_id")
        if not job_id:
            return {
                "status": "failed",
                "progress_pct": 0,
                "error_message": "Falta remote_job_id",
            }
        current = _music_status(job_id)
        if not current:
            return {
                "status": "failed",
                "progress_pct": 0,
                "error_message": "Job remoto no encontrado o expirado",
            }
        return {
            "status": current.get("status", "queued"),
            "progress_pct": current.get("progress_pct", 0),
            "error_message": current.get("error_message"),
            "stems": current.get("stems"),
            **(current.get("result") or {}),
        }

    if request.get("async") is not True:
        return {
            "status": "failed",
            "progress_pct": 0,
            "error_message": "La generación requiere async=true.",
        }

    payload = {**request, "mode": mode}
    try:
        if mode == "from_description":
            GenerateFromDescriptionRequest(**payload)
        elif mode == "with_lyrics":
            GenerateWithCustomLyricsRequest(**payload)
        else:
            GenerateWithDescribedLyricsRequest(**payload)
    except ValidationError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    job_id = _claim_music_job(request.get("client_job_id"))
    _spawn_music_job(payload, job_id)
    current = _music_status(job_id) or {"status": "failed", "progress_pct": 0}
    return {
        "remote_job_id": job_id,
        "status": current.get("status", "queued"),
        "progress_pct": current.get("progress_pct", 0),
    }


@app.function(image=controller_image, secrets=[music_gen_secrets], timeout=120)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def generate_from_description(request: dict):
    return _music_controller(request, "from_description")


@app.function(image=controller_image, secrets=[music_gen_secrets], timeout=120)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def generate_with_lyrics(request: dict):
    return _music_controller(request, "with_lyrics")


@app.function(image=controller_image, secrets=[music_gen_secrets], timeout=120)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def generate_with_described_lyrics(request: dict):
    return _music_controller(request, "with_described_lyrics")


@app.function(image=controller_image, timeout=30)
@modal.fastapi_endpoint(method="GET")
def health():
    return {"status": "ok", "model": "ace-step"}

@app.local_entrypoint()
def main():
    endpoint_url = generate_with_described_lyrics.get_web_url()

    request_data = GenerateWithDescribedLyricsRequest(
        prompt="rave, funk, 140BPM, disco",
        described_lyrics="lyrics about water bottles",
        guidance_scale=15,
    )

    modal_key = os.environ.get("MODAL_KEY")
    modal_secret = os.environ.get("MODAL_SECRET")
    if not modal_key or not modal_secret:
        raise RuntimeError(
            "Define MODAL_KEY y MODAL_SECRET para probar el endpoint protegido."
        )

    response = requests.post(
        endpoint_url,
        json={**request_data.model_dump(), "async": True},
        headers={"Modal-Key": modal_key, "Modal-Secret": modal_secret},
    )
    response.raise_for_status()
    print(f"Submitted: {response.json()}")
