# Security Review Pipeline

Semgrep + Gitleaks → 통합 findings → LLM 트리아지 스켈레톤  
대상: **songeunyeol** (서울) · 스택: Python / C / Java / JS / Flutter / Next.js

## 아키텍처

```
PR 이벤트
  ├─ Gitleaks  → gitleaks.json (+ SARIF)
  ├─ Semgrep   → semgrep.json  (+ SARIF)
  └─ normalize_findings.py → findings.json
        └─ (사람 또는 Agent) triage_prompt.md + findings.json → 한글 트리아지 리포트
```

1. **탐지**: GitHub Actions에서 Gitleaks(시크릿) + Semgrep(코드/시크릿 규칙) 실행  
2. **정규화**: JSON을 단일 `findings.json` 스키마로 병합  
3. **LLM 트리아지**: `scripts/triage_prompt.md`를 시스템 프롬프트로 두고 findings를 입력 → 심각도·오탐·조치·한글 요약

LLM 단계는 CI에 강제 연동하지 않음. 로컬/Agent가 `findings.json` + `triage_prompt.md`를 읽어 수행.

## 통합 Finding 스키마

| 필드 | 설명 |
|------|------|
| `id` | 안정적 ID (`source:rule_id:fingerprint` 해시 기반) |
| `source` | `semgrep` \| `gitleaks` |
| `rule_id` | 규칙 ID |
| `severity` | `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` / `INFO` |
| `file` | 경로 |
| `line` | 시작 라인 |
| `message` | 메시지 |
| `fingerprint` | 중복 제거용 |
| `status` | 기본 `open` |
| `triage_priority` | 1(높음)–5(낮음), 정규화 휴리스틱 |

## 로컬 실행

```bash
# 의존성 (예시)
pip install semgrep
# gitleaks: https://github.com/gitleaks/gitleaks/releases

# Semgrep (configs/semgrep.yaml 또는 레지스트리 룰셋)
semgrep scan --config configs/semgrep.yaml --json -o semgrep.json .
# 또는: semgrep scan --config p/security-audit --config p/secrets --json -o semgrep.json .

# Gitleaks
gitleaks detect --source . --config .gitleaks.toml --report-format json --report-path gitleaks.json || true

# 정규화
python scripts/normalize_findings.py \
  --semgrep semgrep.json \
  --gitleaks gitleaks.json \
  --out findings.json

# LLM 트리아지 (사람/Agent)
# triage_prompt.md 내용을 시스템 프롬프트로, findings.json을 유저 입력으로 전달
```

샘플(빈/최소) 입력:

```bash
python scripts/normalize_findings.py \
  --semgrep samples/semgrep_empty.json \
  --gitleaks samples/gitleaks_empty.json \
  --out /tmp/findings.json
```

## GitHub Actions

워크플로: `.github/workflows/security-review.yml`

- 트리거: `pull_request`
- 작업: Gitleaks + Semgrep → 아티팩트(SARIF/JSON) 업로드 → `normalize_findings.py` → `findings.json` 아티팩트
- Semgrep: `configs/semgrep.yaml`이 있으면 사용, 없으면 `p/security-audit` + `p/secrets`
- Gitleaks: 루트 `.gitleaks.toml` allowlist 스텁

리포지토리 루트에 이 디렉터리 내용을 두거나, 워크플로 경로를 모노레포 구조에 맞게 조정하세요. GitHub는 이미 연결된 상태를 가정합니다.

## 설정 메모

- **Semgrep**: `configs/semgrep.yaml`에 로컬 규칙/포함을 두거나, CI에서 자동으로 `p/security-audit` + `p/secrets` 사용.
- **Gitleaks**: `.gitleaks.toml`은 최소 allowlist 스텁. 팀 경로/테스트 픽스처는 `allowlist`에 추가.
- **Flutter/Dart·Next.js**: Semgrep 커뮤니티/레지스트리 룰과 JS/TS 룰이 대부분 커버. C/Java/Python은 `p/security-audit`에 포함되는 경우가 많음.

## LLM 트리아지 사용법

1. CI 또는 로컬에서 `findings.json` 생성  
2. `scripts/triage_prompt.md`를 시스템 프롬프트로 로드  
3. findings JSON을 컨텍스트로 넣고 모델/에이전트에 트리아지 요청  
4. 출력: 항목별 심각도 재평가, 오탐 가능성, 조치 제안, **한국어 요약**
