오늘 하루 수정/생성된 모든 파일을 Gemma로 자동 리뷰하고 Discord로 알림을 보내줘.

단계:
1. `python .claude/skills/review.py` 를 실행해
2. 스크립트가 완료되고 "Claude Code가 자동으로 이어받아 개선합니다..." 메시지가 나올 때까지 기다려
3. `.reviews/latest_review.json` 파일을 10초마다 확인해
4. `ready_for_claude` 가 `true` 가 될 때까지 대기해 (최대 10분)
5. `true` 가 되면 파일을 읽어서:
   - `files` 배열에 있는 모든 파일 확인
   - `summaries` 에서 각 파일의 Gemma 리뷰 요약 확인
   - `codes` 에서 각 파일의 원본 코드 확인
   - `feedback` 에서 사용자 피드백 확인
6. 각 파일마다 `summaries` 와 `feedback` 을 모두 반영해서 개선해줘
7. 모든 파일 개선 완료 후 변경사항을 파일별로 정리해서 나한테 설명해줘
8. `.reviews/latest_review.json` 의 `ready_for_claude` 를 `false` 로 업데이트해
