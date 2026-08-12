# DGReview

**로컬 LLM(Gemma) → Discord → Claude** 로 이어지는 멀티 모델 코드 리뷰 자동화 파이프라인입니다.
Gemma가 코드를 1차 리뷰해 Discord로 보내면, 사람이 피드백을 남기고, 그 피드백을 반영해 Claude가 최종 개선을 적용합니다.

> "AI 코드리뷰를 어떻게 사람 피드백 루프와 결합할까?"를 실험하며 만든 개인 프로젝트입니다.
> 로컬 추론(Ollama)으로 비용 없이 1차 리뷰를 돌리고, 사람의 판단을 중간에 끼워 넣는 구조가 핵심입니다.

## 동작 흐름

```
[코드 수정]
   ↓
review.py — 변경 파일 감지 → Gemma(Ollama)로 코드 리뷰
   ↓
discord_bot.py — 리뷰 결과를 Discord 채널로 전송
   ↓
[사람이 Discord에서 피드백 반응]
   ↓
.reviews/latest_review.json (ready_for_claude=true 로 전환)
   ↓
Claude가 summary + feedback 을 반영해 파일 개선
```

## 구성

| 파일 | 역할 |
|------|------|
| `review.py` | 변경 파일 감지, Gemma 리뷰 실행, 리뷰 JSON 생성 |
| `gemma.py` | Ollama 로컬 LLM(Gemma) 호출 래퍼 |
| `discord_bot.py` | Discord 봇 — 리뷰 전송 및 사용자 피드백 수집 |
| `dgreview.md` | `/dgreview` 슬래시 커맨드 정의 |
| `CLAUDE.md` | Claude Code용 파이프라인 실행 가이드 |

## 실행 준비

1. Ollama 실행: `ollama serve` (Gemma 모델 필요)
2. `.env.example` 을 `.env` 로 복사하고 Discord 봇 토큰/채널 ID 입력
3. Discord 봇을 서버에 초대
4. Claude Code에서 `/dgreview` 실행

## 기술

Python · Ollama(Gemma) · discord.py · Claude Code 커스텀 커맨드

## 라이선스

MIT — [LICENSE](./LICENSE) 참고.
