"""
gemma.py — Gemma 토론 공통 모듈
Gemma A ↔ Gemma B 다중 라운드 토론
"""

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:26b-a4b"


def ask(prompt: str, role: str = "") -> str:
    """Gemma에게 질문"""
    system = f"너는 {role}야. 한국어로 답해줘. " if role else "한국어로 답해줘. "
    try:
        res = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": system + prompt,
                "stream": False
            },
            timeout=300
        )
        res.raise_for_status()
        return res.json()["response"]
    except requests.exceptions.ConnectionError:
        return "❌ Ollama 연결 실패. `ollama serve` 를 먼저 실행해주세요."
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}"


def debate(code: str, filename: str, rounds: int = 3) -> dict:
    """
    Gemma A ↔ Gemma B 토론
    returns: { history, summary }
    """
    history = []
    print(f"\n🟢 [Gemma A] 첫 번째 분석 중... ({filename})")

    # Gemma A 첫 분석
    current = ask(
        f"파일명: {filename}\n\n"
        f"다음 코드를 분석하고 문제점과 개선 방향을 구체적으로 말해줘:\n"
        f"```\n{code}\n```",
        role="10년 경력의 시니어 개발자"
    )
    history.append({
        "role": "Gemma A",
        "round": 0,
        "label": "첫 분석",
        "content": current
    })
    print(f"   완료 ({len(current)}자)")

    for i in range(rounds):
        round_num = i + 1
        print(f"\n🔵 [Gemma B] 라운드 {round_num} 반박 중...")

        # Gemma B 반박
        b = ask(
            f"다음 코드 분석을 검토해줘:\n{current}\n\n"
            f"이 분석에서:\n"
            f"1. 놓친 부분\n"
            f"2. 동의하지 않는 부분\n"
            f"3. 추가로 개선할 수 있는 부분\n"
            f"을 구체적으로 말해줘. 반드시 새로운 관점을 제시해.",
            role="코드 리뷰 전문가"
        )
        history.append({
            "role": "Gemma B",
            "round": round_num,
            "label": f"라운드 {round_num} 반박",
            "content": b
        })
        print(f"   완료 ({len(b)}자)")

        print(f"\n🟢 [Gemma A] 라운드 {round_num} 재반박 중...")

        # Gemma A 재반박
        current = ask(
            f"피드백을 받았어:\n{b}\n\n"
            f"수용할 부분은 수용하고, 근거 있게 반박할 부분은 반박하면서 "
            f"최선의 개선 방향을 정리해줘.",
            role="10년 경력의 시니어 개발자"
        )
        history.append({
            "role": "Gemma A",
            "round": round_num,
            "label": f"라운드 {round_num} 재반박",
            "content": current
        })
        print(f"   완료 ({len(current)}자)")

    # 최종 요약
    print(f"\n📋 [테크 리드] 최종 요약 작성 중...")
    summary = ask(
        f"지금까지 토론 내용:\n{current}\n\n"
        f"위 내용을 바탕으로:\n"
        f"1. 핵심 문제점 (최대 3가지)\n"
        f"2. 권장 개선 방향 (최대 3가지)\n"
        f"3. 최종 결론 한 줄\n"
        f"로 간결하게 정리해줘.",
        role="테크 리드"
    )
    print(f"   완료")

    return {
        "history": history,
        "summary": summary
    }
