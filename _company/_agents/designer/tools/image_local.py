#!/usr/bin/env python3
"""Draw Things Local Image Generator — image_local.

이 스크립트는 맥미니의 Draw Things 앱에 내장된 Automatic1111 호환 HTTP API를 호출하여
로컬에서 AI 이미지를 생성하고 저장합니다.

자가진단 및 인공지능 프롬프트 최적화, 그리고 활성 모델(SDXL/SD1.5) 해상도 자동 감지 기능이 탑재되어 있습니다.
"""
import os
import json
import sys
import base64
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "image_local.json")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 설정 파일을 읽을 수 없습니다: {e}")
        return {}

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass

def parse_cli_args():
    """커맨드라인 인자에서 프롬프트를 추출합니다."""
    if len(sys.argv) <= 1:
        return None
        
    args = sys.argv[1:]
    
    # --prompt 또는 -p 플래그 처리
    if "--prompt" in args:
        idx = args.index("--prompt")
        if idx + 1 < len(args):
            return args[idx + 1]
    elif "-p" in args:
        idx = args.index("-p")
        if idx + 1 < len(args):
            return args[idx + 1]
            
    # 플래그 없이 전체 텍스트가 인자로 들어온 경우
    return " ".join(args)

def get_env_or_config(cfg, key, default=""):
    """환경 변수(대소문자 무관) -> JSON 설정 파일(대소문자 무관) -> 기본값 순으로 값을 조회합니다."""
    # 1. 환경 변수 조회 (대소문자 구분 없음)
    for k, v in os.environ.items():
        if k.lower() == key.lower() and v.strip():
            return v.strip()
            
    # 2. JSON 설정 조회 (대소문자 구분 없음)
    for k, v in cfg.items():
        if k.lower() == key.lower() and str(v).strip():
            return str(v).strip()
            
    return str(default)

def extract_prompt_from_chat(chat_text):
    """채팅 텍스트에서 이미지 생성 핵심 요구사항을 분리합니다."""
    chat_text = chat_text.replace("\n", " ").strip()
    
    # 1. "사용해서" 또는 "사용하여" 뒤의 핵심 요구사항 분리
    if "사용해서" in chat_text:
        parts = chat_text.split("사용해서", 1)
        content = parts[1].strip()
    elif "사용하여" in chat_text:
        parts = chat_text.split("사용하여", 1)
        content = parts[1].strip()
    else:
        content = chat_text
        
    # 2. "그려", "생성", "만들어", "저장" 등 행위 지시 종결부 제거
    end_markers = ["그려", "생성", "만들어", "저장", "그려줘", "만들어줘", "생성해줘", "해주", "그려서"]
    for marker in end_markers:
        if marker in content:
            content = content.split(marker, 1)[0].strip()
            
    # 양 끝의 따옴표 및 불필요 문자 제거
    content = content.strip("\"'., 💬")
    
    if not content or len(content) > 100:
        return chat_text.strip("\"'., 💬")
        
    return content

def detect_aspect_ratio(chat_text):
    """채팅 텍스트에서 종횡비를 감지하여 (width, height)를 반환합니다."""
    chat_text = chat_text.lower()
    
    # 16:9 (유튜브 썸네일, 가로형)
    if "16:9" in chat_text or "썸네일" in chat_text or "가로형" in chat_text or "유튜브" in chat_text or "가로 비율" in chat_text:
        return 768, 432
        
    # 9:16 (인스타 릴스, 세로형, 쇼츠)
    if "9:16" in chat_text or "릴스" in chat_text or "쇼츠" in chat_text or "세로형" in chat_text or "세로 비율" in chat_text:
        return 432, 768
        
    # 1:1 (인스타그램 게시물, 정사각형)
    if "1:1" in chat_text or "정사각형" in chat_text or "게시물" in chat_text or "인스타" in chat_text or "정사각" in chat_text:
        return 512, 512
        
    return None

def find_prompt_from_latest_chat(workspace_root):
    """최근 대화 파일에서 'image_local'과 관련된 사용자의 지시를 찾아 전체 텍스트를 반환합니다."""
    conv_dir = os.path.join(workspace_root, "_company", "00_Raw", "conversations")
    if not os.path.exists(conv_dir):
        return None
        
    try:
        # 가장 최근 대화 파일 찾기 (오름차순 정렬 후 마지막 파일)
        files = [f for f in os.listdir(conv_dir) if f.endswith(".md")]
        if not files:
            return None
        latest_file = sorted(files)[-1]
        latest_path = os.path.join(conv_dir, latest_file)
        
        with open(latest_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # 역순으로 훑으면서 'image_local'이 언급된 사용자의 대화 줄 찾기
        for line in reversed(lines):
            line_str = line.strip()
            if "image_local" in line_str and ("사용해서" in line_str or "그려" in line_str or "그리" in line_str):
                return line_str
    except Exception as e:
        print(f"⚠️ 대화록 분석 중 오류 발생: {e}")
        
    return None

def query_local_llm_for_parameters(prompt_text, current_cfg):
    """로컬 Ollama를 호출하여 사용자의 요청을 분석하고, Draw Things용 최적화된 전체 JSON 파라미터를 생성합니다."""
    import requests
    ollama_url = "http://127.0.0.1:11434"
    
    # 기본 종횡비 감지
    detected_dims = detect_aspect_ratio(prompt_text)
    default_width = detected_dims[0] if detected_dims else int(current_cfg.get("width") or 512)
    default_height = detected_dims[1] if detected_dims else int(current_cfg.get("height") or 512)
    
    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=3)
        if r.status_code != 200:
            return None
        models = [m["name"] for m in r.json().get("models", [])]
        if not models:
            return None
        model = models[0]
        
        # LLM 지시문 작성
        system_instruction = (
            "You are a master Stable Diffusion prompt engineer and visual designer.\n"
            "Analyze the user's Korean request and return a JSON object with optimized parameters for Stable Diffusion/Draw Things.\n\n"
            "Follow these rules for the JSON fields:\n"
            "1. 'prompt': A highly detailed, visually descriptive English prompt containing quality modifiers, lightings, specific settings, and art styles.\n"
            "2. 'negative_prompt': Standard negative keywords (e.g. 'ugly, blurry...'), plus any style-specific negative keywords (e.g., if illustration, avoid 'photorealistic').\n"
            "3. 'width' and 'height': Integers. Match the user's ratio request (e.g., 768x432 for 16:9, 432x768 for 9:16, 512x512 for 1:1).\n"
            "4. 'steps': Integer between 20 and 50 (Higher steps for complex visual designs, lower for simple illustrations).\n"
            "5. 'cfg_scale': Float between 6.0 and 12.0 representing Text Guidance (CFG scale).\n"
            "6. 'sampler_name': String representing the optimal sampler (choose from: 'Euler a', 'DPM++ 2M Karras', 'Heun', 'DDIM').\n"
            "7. 'seed': Integer. Use -1 for random, unless the user explicitly specified a seed number.\n\n"
            "Output ONLY valid JSON. Do not include any explanations, comments, or markdown formatting."
        )
        
        template = {
            "prompt": "Masterpiece English prompt...",
            "negative_prompt": "ugly, blurry...",
            "width": default_width,
            "height": default_height,
            "steps": 30,
            "cfg_scale": 8.0,
            "sampler_name": "DPM++ 2M Karras",
            "seed": -1
        }
        
        user_prompt = f"User Request: {prompt_text}\nJSON Template: {json.dumps(template)}\nResponse JSON:"
        
        payload = {
            "model": model,
            "prompt": f"{system_instruction}\n\n{user_prompt}",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 400
            }
        }
        
        resp = requests.post(f"{ollama_url}/api/generate", json=payload, timeout=30)
        if resp.status_code == 200:
            raw_response = resp.json().get("response", "").strip()
            match = re.search(r"\{.*\}", raw_response, re.DOTALL)
            if match:
                json_str = match.group(0)
                parsed = json.loads(json_str)
                return {
                    "prompt": str(parsed.get("prompt", "")),
                    "negative_prompt": str(parsed.get("negative_prompt", "")),
                    "width": int(parsed.get("width", default_width)),
                    "height": int(parsed.get("height", default_height)),
                    "steps": int(parsed.get("steps", 30)),
                    "cfg_scale": float(parsed.get("cfg_scale", 8.0)),
                    "sampler_name": str(parsed.get("sampler_name", "DPM++ 2M Karras")),
                    "seed": int(parsed.get("seed", -1))
                }
    except Exception:
        pass
    return None

def offline_fallback_enhance(prompt_text):
    """로컬 LLM 호출에 실패할 경우, 오프라인 규칙 기반으로 최적화 및 퀄리티 태그를 덧붙입니다."""
    en_prompt = prompt_text
    translations = {
        "강아지": "a cute fluffy puppy",
        "도서관": "mysterious fantasy library, glowing magic books, ancient bookshelves",
        "판타지": "fantasy mystical concept art",
        "일러스트": "vibrant colors illustration",
        "마법": "magic, mystical particles"
    }
    
    matched = []
    for ko, en in translations.items():
        if ko in prompt_text:
            matched.append(en)
            
    if matched:
        en_prompt = ", ".join(matched)
        
    return f"{en_prompt}, beautiful warm lighting, highly detailed, digital art, masterpiece, 8k resolution, trending on artstation"

def main():
    cfg = load_config()
    workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

    # 1. 대화록에서 최신 사용자 지시사항 확인
    latest_chat = find_prompt_from_latest_chat(workspace_root)
    last_processed_chat = cfg.get("last_processed_chat", "")
    
    is_new_request = (latest_chat is not None) and (latest_chat != last_processed_chat)
    
    # 2. 신규 요청이 감지되었을 경우 모든 설정 최적화 및 로드
    if is_new_request:
        print(f"🔔 [신규 요청 감지] 새로운 사용자 지시를 분석하여 이미지 설정을 최적화합니다:")
        print(f"   └─ 대화 줄: \"{latest_chat.strip('\" 💬')}\"")
        
        print(f"🧠 [로컬 LLM] 생성 파라미터 종합 최적화 분석 중...")
        optimized = query_local_llm_for_parameters(latest_chat, cfg)
        
        if optimized:
            cfg["prompt"] = optimized["prompt"]
            cfg["negative_prompt"] = optimized["negative_prompt"]
            cfg["width"] = str(optimized["width"])
            cfg["height"] = str(optimized["height"])
            cfg["steps"] = str(optimized["steps"])
            cfg["cfg_scale"] = str(optimized["cfg_scale"])
            cfg["sampler_name"] = optimized["sampler_name"]
            cfg["seed"] = str(optimized["seed"])
            
            prompt = optimized["prompt"]
            width = optimized["width"]
            height = optimized["height"]
            steps = optimized["steps"]
            cfg_scale = optimized["cfg_scale"]
            sampler_name = optimized["sampler_name"]
            seed = optimized["seed"]
        else:
            raw_prompt = extract_prompt_from_chat(latest_chat)
            dimensions = detect_aspect_ratio(latest_chat)
            
            if dimensions:
                width, height = dimensions
                cfg["width"] = str(width)
                cfg["height"] = str(height)
            else:
                width = int(cfg.get("width") or 512)
                height = int(cfg.get("height") or 512)
                
            prompt = offline_fallback_enhance(raw_prompt)
            print(f"   └─ 로컬 LLM 연결 실패로 자가 번역/종횡비 폴백 적용: {prompt}")
            
            cfg["prompt"] = prompt
            cfg["negative_prompt"] = "ugly, blurry, low quality, distorted, bad hands, low resolution"
            cfg["steps"] = "20"
            cfg["cfg_scale"] = "7.0"
            cfg["sampler_name"] = "Euler a"
            cfg["seed"] = "-1"
            
            steps = 20
            cfg_scale = 7.0
            sampler_name = "Euler a"
            seed = -1
            
        cfg["last_processed_chat"] = latest_chat
        save_config(cfg)
        
    else:
        prompt = get_env_or_config(cfg, "prompt", "").strip()
        width = int(get_env_or_config(cfg, "width", 512))
        height = int(get_env_or_config(cfg, "height", 512))
        steps = int(get_env_or_config(cfg, "steps", 20))
        cfg_scale = float(get_env_or_config(cfg, "cfg_scale", 7.0))
        sampler_name = get_env_or_config(cfg, "sampler_name", "Euler a")
        seed = int(get_env_or_config(cfg, "seed", -1))

    # CLI 및 기타 폴백 체크
    cli_prompt = parse_cli_args()
    if cli_prompt:
        prompt = cli_prompt.strip()

    if not prompt:
        print("⚠️  PROMPT(이미지 설명)가 비어있어요. image_local.json 에 생성하고 싶은 그림을 묘사해 주세요.")
        sys.exit(1)

    # 3. 기타 세부 설정값 로드
    draw_things_url = get_env_or_config(cfg, "draw_things_url", "http://127.0.0.1:7860").rstrip("/")
    neg_prompt = get_env_or_config(cfg, "negative_prompt", "ugly, blurry, low quality, distorted, bad hands, low resolution").strip()
    output_filename = get_env_or_config(cfg, "output_filename", "generated_image.png").strip()

    # 4. 🌟 초강력 SDXL 표준 규격(1024px) 해상도 왜곡 자동 보정 기능 🌟
    try:
        import requests
        opt_resp = requests.get(f"{draw_things_url}/sdapi/v1/options", timeout=3)
        if opt_resp.status_code == 200:
            active_model = opt_resp.json().get("model", "").lower()
            # 모델명에 sdxl, illust, pony, x16 등이 있으면 SDXL로 판단하여 강제로 해상도 2배 업스케일
            if "sdxl" in active_model or "illust" in active_model or "pony" in active_model:
                print(f"📡 [모델 분석] 현재 Draw Things 활성 모델: {active_model}")
                print("⚠️  [해상도 왜곡 방지] SDXL 기반 고품질 모델이 감지되었습니다!")
                
                # 512x512 -> 1024x1024로 변환하여 SDXL의 깨짐/세로줄무늬 오작동 방지
                if width <= 512 and height <= 512:
                    width = 1024
                    height = 1024
                    print("   └─ 해상도 자동 조율: 512x512 정사각형 -> 1024x1024 2배 업스케일 적용 ✓")
                elif width == 768 and height == 432:
                    width = 1024
                    height = 576
                    print("   └─ 해상도 자동 조율: 16:9 유튜브 비율 -> 1024x576 업스케일 적용 ✓")
                elif width == 432 and height == 768:
                    width = 576
                    height = 1024
                    print("   └─ 해상도 자동 조율: 9:16 세로형 비율 -> 576x1024 업스케일 적용 ✓")
    except Exception as e:
        pass

    print(f"\n🎨 [로컬 Draw Things] 이미지 생성 시작...")
    print(f"  └─ API 주소: {draw_things_url}")
    print(f"  └─ 프롬프트: {prompt}")
    print(f"  └─ 크기: {width} x {height} | 스텝: {steps} | CFG (텍스트가이드): {cfg_scale}")
    print(f"  └─ 샘플러: {sampler_name} | 시드 (Seed): {seed}")

    # API 호출용 페이로드 구성 (Automatic1111 호환)
    payload = {
        "prompt": prompt,
        "negative_prompt": neg_prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "sampler_name": sampler_name,
        "seed": seed,
    }

    try:
        # Draw Things의 Automatic1111 호환 txt2img 엔드포인트 호출
        api_endpoint = f"{draw_things_url}/sdapi/v1/txt2img"
        response = requests.post(api_endpoint, json=payload, timeout=600)
        response.raise_for_status()
    except Exception as e:
        print("\n❌ Draw Things 앱 연결 실패!")
        print("   ┌─────────────────────────────────────────────────────────────┐")
        print("   │  💡 해결 가이드:                                            │")
        print("   │  1. 맥미니에서 Draw Things 앱이 켜져 있는지 확인하세요.     │")
        print("   │  2. 설정(Gear 아이콘) -> Advanced 또는 HTTP API Server      │")
        print("   │     메뉴를 찾아 'Enable API Server'를 꼭 활성화하세요.       │")
        print("   │  3. 기본 포트는 7860입니다. (http://127.0.0.1:7860)         │")
        print("   │  4. 앱이 재시작될 때마다 서버를 켜 주어야 할 수 있습니다.   │")
        print("   └─────────────────────────────────────────────────────────────┘")
        print(f"   (상세 오류: {e})")
        sys.exit(1)

    try:
        res_json = response.json()
        images = res_json.get("images", [])
        if not images:
            print("❌ 생성된 이미지 데이터가 응답에 없습니다.")
            sys.exit(1)
            
        # 첫 번째 이미지 base64 디코딩
        img_data = base64.b64decode(images[0])
        
        # 저장 폴더 결정 (_company/assets 폴더 우선, 없으면 workspace 루트)
        assets_dir = os.path.join(workspace_root, "_company", "assets")
        
        if not os.path.exists(assets_dir):
            try:
                os.makedirs(assets_dir, exist_ok=True)
            except Exception:
                assets_dir = workspace_root # 생성 불가 시 루트 폴더에 저장

        output_path = os.path.join(assets_dir, output_filename)
        
        with open(output_path, "wb") as f:
            f.write(img_data)
            
        print(f"\n🎉 [성공] 이미지 생성이 완료되었습니다!")
        print(f"💾 저장된 경로: {output_path}")
        print(f"💡 디렉토리 상대 경로: _company/assets/{output_filename}")
        
    except Exception as e:
        print(f"❌ 이미지 저장 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
