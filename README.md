# Darkest Dungeon PS Vita 한글패치 v0.9.1

## 게임 및 패치 정보

| 항목 | 내용 |
| --- | --- |
| 게임 | Darkest Dungeon (다키스트 던전) |
| 플랫폼 | PlayStation Vita |
| 패치 대상 | **PCSG01154** |
| 설치 방식 | rePatch |
| 현재 버전 | **0.9.1** |

## 한글패치 소개

PCSG01154에 한국어를 적용한 비공식 패치입니다. 사용자가 보유한 Nintendo Switch판 업데이트의 한국어 데이터와 글꼴을 PS Vita 데이터 형식에 맞게 변환했습니다.

실기에서 한글 표시와 띄어쓰기, 전투 숫자 및 상태 문구 표시를 확인했습니다. v0.9.1에서는 전투 표시의 색 대비를 높이고 글자 획을 얇게 조정했으며, 조정 결과를 실기에서 확인했습니다. 튜토리얼 설명처럼 작은 글자는 다소 흐릿하게 보일 수 있으며, 전체 게임 진행과 모든 화면을 확인한 상태는 아닙니다.

## 다운로드

[v0.9.1 릴리스](https://github.com/YourFaceMonster/darkest-dungeon-psv-korean-patch/releases/tag/v0.9.1)의 `content.psarc`를 받으세요. 압축 해제 없이 바로 복사할 수 있습니다. 직접 빌드하면 `dist/v0.9.1/rePatch/PCSG01154/content.psarc`가 생성됩니다. 게임 데이터가 포함된 결과물은 Git 저장소에 넣지 않습니다.

## 설치 방법

대상 타이틀 ID는 **PCSG01154**이며, 기기에 rePatch가 활성화되어 있어야 합니다.

1. 게임을 완전히 종료합니다.
2. 기존 `ux0:rePatch/PCSG01154` 폴더가 있다면 백업합니다.
3. 받은 `content.psarc`를 PS Vita의 `ux0:rePatch/PCSG01154/` 폴더에 복사합니다. 직접 빌드했다면 `dist/v0.9.1/rePatch` 폴더를 `ux0:` 최상위에 복사해도 됩니다.
4. `ux0:rePatch/PCSG01154/content.psarc`가 있는지 확인합니다.
5. 게임을 실행합니다.

## 실기 확인 및 알려진 문제

- 한국어 글자 표시와 띄어쓰기를 확인했습니다.
- 전투 숫자와 상태 문구, v0.9.1의 획 조정 결과를 실기에서 확인했습니다.
- 튜토리얼 팝업 등 일부 작은 설명 글자는 선명도가 떨어질 수 있습니다.
- 전체 플레이와 모든 DLC의 호환성은 아직 확인하지 않았습니다.

문제가 발생하면 오류 화면, 발생 시점, 게임 업데이트 버전, 적용한 rePatch 파일과 화면 사진을 함께 남겨주세요.

## 복구

게임을 종료한 뒤 `ux0:rePatch/PCSG01154` 폴더를 다른 위치로 옮기고, 백업한 폴더가 있으면 복원합니다.

## 직접 빌드하기

이 저장소에는 게임 원본과 Switch판 한국어 데이터가 포함되지 않습니다. 본인이 보유한 PS Vita판 `content.psarc`와 Nintendo Switch 업데이트에서 추출한 `romfs`가 필요합니다. Switch 입력 자료는 약 70MB입니다. `romfs`에는 `localization/koreana.loc2`와 `fonts/korean_ubuntu.fnt`가 있어야 합니다.

Python 3.10 이상에서:

```powershell
python -m pip install -r requirements.txt
python build_patch.py --vita "D:\path\content.psarc" --switch "D:\path\romfs"
```

출력 경로: `dist/v0.9.1/rePatch/PCSG01154/content.psarc`

## 제작 및 출처

- **YourFaceMonster** — 프로젝트 진행, PS Vita 실기 확인 및 배포
- **Codex (OpenAI)** — 파일 구조 분석, 데이터·글꼴 변환 및 패키지 제작 지원
- **Red Hook Studios** — 원작 게임 개발
- Nintendo Switch판 한국어 데이터와 글꼴 — 사용자가 보유한 게임 업데이트에서 추출

이 저장소는 비공식 팬 패치 제작 자료입니다. 게임 및 번역 자료에 임의의 오픈소스 라이선스를 부여하지 않습니다.

