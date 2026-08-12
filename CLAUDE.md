# 🤖 DGReview 자동화 시스템

## 개요
Gemma AI가 코드를 자동으로 리뷰하고, Discord로 결과를 전송하여
사용자 피드백을 받은 뒤 Claude가 최종 개선을 적용하는 파이프라인입니다.

## 사용 방법

### /dgreview
직전에 수정한 파일을 자동으로 감지하여 전체 리뷰 파이프라인을 실행합니다.

**실행 순서:**
1. `python .claude/skills/review.py` 를 실행해
2. 스크립트가 완료될 때까지 기다려 (Discord 알림 전송까지)
3. `.reviews/latest_review.json` 파일을 주기적으로 확인해
4. `ready_for_claude` 가 `true` 가 될 때까지 10초마다 확인해 (최대 10분)
5. `ready_for_claude` 가 `true` 가 되면 파일을 읽어
6. `filename` 에 해당하는 파일을 열어
7. `summary` 와 `feedback` 을 모두 반영해서 파일을 개선해줘
8. 개선 완료 후 변경된 부분을 diff 형식으로 나한테 설명해줘
9. `.reviews/latest_review.json` 의 `ready_for_claude` 를 `false` 로 업데이트해

## 주의사항
- Ollama가 실행 중이어야 합니다: `ollama serve`
- Discord 봇이 서버에 초대되어 있어야 합니다
- git으로 관리되는 프로젝트에서 실행해야 합니다
- `.env` 파일에 DISCORD_TOKEN, DISCORD_CHANNEL_ID 가 설정되어 있어야 합니다
