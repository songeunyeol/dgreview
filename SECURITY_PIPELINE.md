# Security Review Pipeline (DGReview 연동)

Semgrep + Gitleaks → `findings.json` → LLM 트리아지 레이어.

기존 DGReview 흐름(Gemma → Discord → Claude) 옆에 **정적 보안 스캔**을 붙인 것이다.

## 흐름

```
PR / 로컬 스캔
  ├─ Gitleaks  → gitleaks.json
  ├─ Semgrep   → semgrep.json
  └─ scripts/normalize_findings.py → findings.json
        └─ scripts/triage_prompt.md + LLM(Gemma/Claude/에이전트)
              └─ (선택) Discord로 트리아지 요약 → 사람 피드백
```

## DGReview와의 역할 분담

| 단계 | 도구 | 역할 |
|------|------|------|
| 코드 리뷰 | `review.py` + Gemma | 오늘 변경 파일의 품질·버그 토론 |
| 보안 탐지 | GHA `security-review.yml` | 시크릿·SAST 규칙 탐지 |
| 보안 트리아지 | `triage_prompt.md` + LLM | 오탐/심각도/조치 (한국어) |
| 사람 루프 | Discord | 승인·거절·추가 피드백 |

트리아지는 CI에 API 키를 넣지 않는다. 아티팩트 `findings.json`을 받은 뒤 로컬 Ollama(Gemma)나 Claude/에이전트가 `triage_prompt.md`를 시스템 프롬프트로 쓰면 된다.

## 로컬 스모크

```bash
python scripts/normalize_findings.py \
  --semgrep samples/semgrep_sample.json \
  --gitleaks samples/gitleaks_sample.json \
  --out findings.json
```

## 다음 단계 (제안)

1. Actions 활성화 후 이 PR로 워크플로 한 번 돌려 보기
2. `review.py`에 `findings.json`이 있으면 Discord 메시지에 보안 요약 섹션 붙이기 (후속)
3. `focus-cash` 등 앱 레포에는 이 워크플로만 복사해 재사용
