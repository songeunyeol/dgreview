"""
review.py — DGReview 메인 실행 파일

오늘 하루 수정/생성된 모든 파일을 감지하여
Gemma 토론 후 Discord로 결과 전송,
사용자 피드백 대기 후 Claude에게 전달
"""

import subprocess
import sys
import json
import time
import os
from pathlib import Path
from datetime import datetime, date

# 경로 설정
SKILLS_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILLS_DIR))

from gemma import debate
from discord_bot import start_bot, send_to_discord, PENDING_FILE

# ── 설정 ──────────────────────────────────────────
REVIEWS_DIR = Path(".reviews")
LATEST_REVIEW = REVIEWS_DIR / "latest_review.json"

# 리뷰 대상 확장자
TARGET_EXTENSIONS = {
    ".py", ".dart", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".kt", ".swift", ".go", ".rs",
    ".c", ".cpp", ".h", ".cs", ".php", ".rb"
}

# 무시할 폴더
IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".dart_tool",
    "build", "dist", ".reviews", ".claude", "venv", ".env"
}


# ── 오늘 수정/생성된 파일 감지 ────────────────────
def get_today_files() -> list[str]:
    """오늘 하루 수정되거나 새로 생성된 모든 파일 반환"""
    today = date.today().isoformat()
    today_files = []

    methods = [
        _get_files_from_git_today,
        _get_files_from_filesystem_today,
    ]

    for method in methods:
        files = method()
        if files:
            today_files = files
            print(f"   감지 방법: {method.__name__}")
            break

    # 중복 제거 + 정렬
    today_files = sorted(set(today_files))
    return today_files


def _get_files_from_git_today() -> list[str]:
    """git log로 오늘 커밋된 파일 + 현재 수정 중인 파일"""
    files = set()
    today = date.today().isoformat()

    try:
        # 오늘 커밋된 파일
        result = subprocess.run(
            ["git", "log", "--since", f"{today} 00:00:00",
             "--until", f"{today} 23:59:59",
             "--name-only", "--pretty=format:"],
            capture_output=True, text=True, timeout=10
        )
        for f in result.stdout.strip().split("\n"):
            f = f.strip()
            if f and Path(f).suffix in TARGET_EXTENSIONS:
                files.add(f)

        # 현재 수정 중인 파일 (커밋 안된 것 포함)
        for cmd in [
            ["git", "diff", "--name-only", "HEAD"],
            ["git", "diff", "--name-only"],
            ["git", "ls-files", "--others", "--exclude-standard"],  # 새 파일
        ]:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10
            )
            for f in result.stdout.strip().split("\n"):
                f = f.strip()
                if f and Path(f).suffix in TARGET_EXTENSIONS:
                    files.add(f)

    except Exception as e:
        print(f"   git 감지 실패: {e}")
        return []

    return [f for f in files if Path(f).exists()]


def _get_files_from_filesystem_today() -> list[str]:
    """파일 수정 시간 기준으로 오늘 변경된 파일 탐색"""
    files = []
    today_start = datetime.combine(date.today(), datetime.min.time()).timestamp()

    for root, dirs, filenames in os.walk("."):
        # 무시할 폴더 제외
        dirs[:] = [
            d for d in dirs
            if d not in IGNORE_DIRS and not d.startswith(".")
        ]

        for filename in filenames:
            filepath = Path(root) / filename
            if filepath.suffix not in TARGET_EXTENSIONS:
                continue
            try:
                mtime = filepath.stat().st_mtime
                if mtime >= today_start:
                    files.append(str(filepath))
            except Exception:
                continue

    return files


# ── 파일 읽기 ──────────────────────────────────────
def read_file(filepath: str) -> str | None:
    """파일 내용 읽기"""
    try:
        return Path(filepath).read_text(encoding="utf-8")
    except Exception as e:
        print(f"   ❌ 파일 읽기 실패 ({filepath}): {e}")
        return None


# ── 피드백 대기 ────────────────────────────────────
def wait_for_feedback(timeout: int = 600) -> dict:
    """Discord 피드백 대기 (기본 10분)"""
    print(f"\n⏳ Discord에서 피드백 대기 중... (최대 {timeout//60}분)")
    print("   Discord에서 !feedback [내용] 또는 !approve 를 입력해주세요.\n")

    start = time.time()
    dots = 0

    while time.time() - start < timeout:
        if PENDING_FILE.exists():
            try:
                data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
                if data.get("status") in ("approved", "rejected"):
                    print()  # 줄바꿈
                    return data
            except Exception:
                pass

        # 진행 표시
        dots = (dots + 1) % 4
        print(f"\r   대기 중{'.' * dots}   ", end="", flush=True)
        time.sleep(3)

    print()
    return {"status": "timeout", "feedback": None}


# ── 메인 실행 ──────────────────────────────────────
def main():
    REVIEWS_DIR.mkdir(exist_ok=True)

    print("=" * 50)
    print("🚀 DGReview 자동화 시스템 시작")
    print(f"📅 날짜: {date.today().isoformat()}")
    print("=" * 50)

    # 1. 오늘 수정/생성된 파일 감지
    print("\n🔍 오늘 수정/생성된 파일 감지 중...")
    files = get_today_files()

    if not files:
        print("❌ 오늘 수정된 파일이 없어요.")
        print("   git으로 관리되는 프로젝트인지 확인해주세요.")
        return

    print(f"\n📁 감지된 파일 ({len(files)}개):")
    for f in files:
        print(f"   • {f}")

    # 2. 파일별 코드 수집
    file_contents = {}
    for filepath in files:
        code = read_file(filepath)
        if code:
            file_contents[filepath] = code

    if not file_contents:
        print("❌ 읽을 수 있는 파일이 없어요.")
        return

    total_chars = sum(len(c) for c in file_contents.values())
    print(f"\n✅ 총 {len(file_contents)}개 파일, {total_chars:,}자 로드 완료")

    # 3. Discord 봇 시작
    print("\n🤖 Discord 봇 시작 중...")
    start_bot()
    time.sleep(2)

    # 4. 파일별 Gemma 토론
    all_results = {}

    for i, (filepath, code) in enumerate(file_contents.items(), 1):
        print(f"\n{'='*50}")
        print(f"📄 [{i}/{len(file_contents)}] 리뷰 중: {filepath}")
        print("=" * 50)

        result = debate(code, filepath, rounds=3)
        all_results[filepath] = {
            "code": code,
            "result": result
        }

    # 5. 전체 종합 요약
    print(f"\n📊 전체 종합 요약 생성 중...")
    all_summaries = "\n\n".join([
        f"[{fp}]\n{data['result']['summary']}"
        for fp, data in all_results.items()
    ])

    # 6. Discord로 전송
    print(f"\n📨 Discord로 결과 전송 중...")
    send_to_discord(all_results, all_summaries, date.today().isoformat())
    print("✅ Discord 전송 완료!")

    # 7. 피드백 대기
    feedback_data = wait_for_feedback()

    if feedback_data["status"] == "rejected":
        print("🗑️ 리뷰가 거절됐어요.")
        PENDING_FILE.unlink(missing_ok=True)
        return

    if feedback_data["status"] == "timeout":
        print("⏰ 타임아웃으로 종료됐어요.")
        return

    # 8. Claude에게 전달할 최종 데이터 저장
    final_data = {
        "date": date.today().isoformat(),
        "files": list(file_contents.keys()),
        "summaries": {
            fp: data["result"]["summary"]
            for fp, data in all_results.items()
        },
        "codes": {
            fp: data["code"]
            for fp, data in all_results.items()
        },
        "feedback": feedback_data.get("feedback"),
        "ready_for_claude": True,
        "timestamp": datetime.now().isoformat()
    }

    LATEST_REVIEW.write_text(
        json.dumps(final_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"\n{'='*50}")
    print("🎯 Claude에게 전달 준비 완료!")
    print(f"📄 결과 파일: {LATEST_REVIEW}")
    print(f"💬 피드백: {feedback_data.get('feedback', '없음')}")
    print(f"📁 대상 파일: {len(file_contents)}개")
    print("=" * 50)
    print("\n✅ Claude Code가 자동으로 이어받아 개선합니다...")


if __name__ == "__main__":
    main()
